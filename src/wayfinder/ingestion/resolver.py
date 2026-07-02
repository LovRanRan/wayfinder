"""Resolve repo inputs into local repo handles."""

import os
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import urlparse

from wayfinder.ingestion.models import (
    CacheCleanupPlan,
    CacheEntry,
    CachePolicy,
    GitHubRepoRef,
    RepoHandle,
    RepoSamplingProposal,
    RepoSizeAssessment,
    RepoSizePolicy,
    RepoSource,
)

IGNORED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".next",
    "dist",
    "build",
}


DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "wayfinder" / "repos"


GitRunner = Callable[[list[str], Path | None], None]


def resolve_repo_source(
    source: RepoSource,
    cache_root: Path | None = None,
    git_runner: GitRunner | None = None,
    allowed_roots: Sequence[Path] | None = None,
) -> RepoHandle:
    if source.kind == "github":
        return resolve_github_repo_source(
            source,
            cache_root or DEFAULT_CACHE_ROOT,
            git_runner or run_git_command,
        )

    repo_path = Path(source.original_ref).expanduser().resolve()

    if not repo_path.exists():
        raise ValueError(f"Repo path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Repo path is not a directory: {repo_path}")

    _enforce_local_repo_root(repo_path, allowed_roots)

    return RepoHandle(
        source=source,
        local_path=repo_path,
        file_count=count_files(repo_path),
    )


def _enforce_local_repo_root(
    repo_path: Path,
    allowed_roots: Sequence[Path] | None,
) -> None:
    """Reject local repo paths outside an operator-configured allowlist.

    Without this, a request such as ``repo_url=../../../etc`` would resolve and be
    read by downstream scanners. When ``allowed_roots`` is None the caller has
    opted out of the guard (single-user dev/tests); when it is an empty sequence
    all local paths are denied, which is the safe default for a multi-tenant
    deployment that should only read cloned GitHub repos.
    """

    if allowed_roots is None:
        return

    resolved_roots = [root.expanduser().resolve() for root in allowed_roots]
    for root in resolved_roots:
        if repo_path == root or repo_path.is_relative_to(root):
            return

    raise PermissionError(
        f"Local repo path {repo_path} is outside the allowed roots. "
        "Set WAYFINDER_LOCAL_REPO_ROOTS to permit local filesystem ingestion."
    )


def resolve_github_repo_source(
    source: RepoSource,
    cache_root: Path,
    git_runner: GitRunner,
) -> RepoHandle:
    repo_ref = parse_github_repo_ref(source)
    local_path = cache_root / repo_ref.cache_key

    materialize_github_repo(repo_ref, local_path, git_runner)

    return RepoHandle(
        source=source,
        local_path=local_path,
        cache_key=repo_ref.cache_key,
        clone_url=repo_ref.clone_url,
        checkout_ref=repo_ref.requested_ref,
        file_count=count_files(local_path),
    )


def parse_github_repo_ref(source: RepoSource) -> GitHubRepoRef:
    parsed = urlparse(source.original_ref)

    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
        raise ValueError(f"Unsupported GitHub repo URL: {source.original_ref}")

    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(path_parts) != 2:
        raise ValueError(
            "GitHub repo URL must point to a repo root like "
            "https://github.com/owner/repo"
        )

    owner = path_parts[0]
    repo = path_parts[1].removesuffix(".git")

    if not owner or not repo:
        raise ValueError(f"Invalid GitHub repo URL: {source.original_ref}")

    cache_key = f"github.com__{owner}__{repo}"

    return GitHubRepoRef(
        owner=owner,
        repo=repo,
        clone_url=f"https://github.com/{owner}/{repo}.git",
        cache_key=cache_key,
        requested_ref=source.requested_ref,
    )


def count_files(repo_path: Path) -> int:
    file_count = 0
    for _root, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in IGNORED_DIRS]
        file_count += len(filenames)

    return file_count


def plan_cache_cleanup(cache_root: Path, policy: CachePolicy) -> CacheCleanupPlan:
    entries = list_cache_entries(cache_root)
    total_bytes = sum(entry.size_bytes for entry in entries)

    entries_to_remove: list[CacheEntry] = []
    remaining_repos = len(entries)
    remaining_bytes = total_bytes

    for entry in sorted(entries, key=lambda item: item.last_used_at):
        if remaining_repos <= policy.max_repos and remaining_bytes <= policy.max_bytes:
            break

        entries_to_remove.append(entry)
        remaining_repos -= 1
        remaining_bytes -= entry.size_bytes

    return CacheCleanupPlan(
        cache_root=cache_root,
        total_repos=len(entries),
        total_bytes=total_bytes,
        entries_to_remove=entries_to_remove,
    )


def list_cache_entries(cache_root: Path) -> list[CacheEntry]:
    if not cache_root.exists():
        return []

    entries: list[CacheEntry] = []
    for path in cache_root.iterdir():
        if not path.is_dir():
            continue

        entries.append(
            CacheEntry(
                cache_key=path.name,
                path=path,
                size_bytes=directory_size_bytes(path),
                last_used_at=path.stat().st_mtime,
            )
        )

    return entries


def directory_size_bytes(path: Path) -> int:
    total = 0
    for root, _dirnames, filenames in os.walk(path):
        root_path = Path(root)
        for filename in filenames:
            try:
                total += (root_path / filename).stat().st_size
            except OSError:
                continue

    return total


def assess_repo_size(
    handle: RepoHandle,
    policy: RepoSizePolicy | None = None,
) -> RepoSizeAssessment:
    policy = policy or RepoSizePolicy()

    if handle.file_count is None:
        return RepoSizeAssessment(
            file_count=None,
            max_files=policy.max_files,
            is_oversized=False,
            sampling_proposal=None,
        )

    if handle.file_count <= policy.max_files:
        return RepoSizeAssessment(
            file_count=handle.file_count,
            max_files=policy.max_files,
            is_oversized=False,
            sampling_proposal=None,
        )

    return RepoSizeAssessment(
        file_count=handle.file_count,
        max_files=policy.max_files,
        is_oversized=True,
        sampling_proposal=RepoSamplingProposal(
            reason=(
                f"Repo has {handle.file_count} files, which exceeds "
                f"the {policy.max_files} file limit."
            ),
            sampling_limit=policy.sampling_limit,
        ),
    )


def run_git_command(args: list[str], cwd: Path | None = None) -> None:
    try:
        subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        raise RuntimeError(f"Git command failed: {' '.join(args)}\n{stderr}") from exc


def materialize_github_repo(
    repo_ref: GitHubRepoRef,
    local_path: Path,
    git_runner: GitRunner,
) -> None:
    if not local_path.exists():
        local_path.parent.mkdir(parents=True, exist_ok=True)
        git_runner(["git", "clone", "--depth", "1", repo_ref.clone_url, str(local_path)], None)
    elif not (local_path / ".git").exists():
        raise ValueError(f"Cache path exists but is not a git repo: {local_path}")

    if repo_ref.requested_ref is not None:
        git_runner(["git", "fetch", "--depth", "1", "origin", repo_ref.requested_ref], local_path)
        git_runner(["git", "checkout", "--detach", "FETCH_HEAD"], local_path)
