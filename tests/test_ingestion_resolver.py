import os
from collections.abc import Callable
from pathlib import Path

import pytest

from wayfinder.ingestion.models import CachePolicy, RepoHandle, RepoSizePolicy, RepoSource
from wayfinder.ingestion.resolver import (
    assess_repo_size,
    parse_github_repo_ref,
    plan_cache_cleanup,
    resolve_repo_source,
)


def test_resolve_local_repo(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n")

    handle = resolve_repo_source(RepoSource(kind="local", original_ref=str(tmp_path)))

    assert handle.local_path == tmp_path.resolve()
    assert handle.file_count == 1
    assert handle.cache_key is None
    assert handle.clone_url is None
    assert handle.checkout_ref is None


def test_missing_local_repo_raises() -> None:
    source = RepoSource(kind="local", original_ref="/definitely/missing/repo")

    with pytest.raises(ValueError, match="does not exist"):
        resolve_repo_source(source)


def test_file_path_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "not_repo.py"
    file_path.write_text("print('hello')\n")

    source = RepoSource(kind="local", original_ref=str(file_path))

    with pytest.raises(ValueError, match="not a directory"):
        resolve_repo_source(source)


def test_count_files_skips_generated_dirs(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n")

    generated_dir = tmp_path / "node_modules" / "pkg"
    generated_dir.mkdir(parents=True)
    (generated_dir / "ignored.js").write_text("console.log('skip')\n")

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

    handle = resolve_repo_source(RepoSource(kind="local", original_ref=str(tmp_path)))

    assert handle.file_count == 1


def test_parse_github_repo_url() -> None:
    source = RepoSource(kind="github", original_ref="https://github.com/langchain-ai/langchain.git")

    repo_ref = parse_github_repo_ref(source)

    assert repo_ref.owner == "langchain-ai"
    assert repo_ref.repo == "langchain"
    assert repo_ref.clone_url == "https://github.com/langchain-ai/langchain.git"
    assert repo_ref.cache_key == "github.com__langchain-ai__langchain"


def test_parse_github_repo_ref_preserves_requested_ref() -> None:
    source = RepoSource(
        kind="github",
        original_ref="https://github.com/langchain-ai/langchain",
        requested_ref="v0.3.0",
    )

    repo_ref = parse_github_repo_ref(source)

    assert repo_ref.requested_ref == "v0.3.0"


def test_resolve_github_repo_returns_cache_contract(tmp_path: Path) -> None:
    calls: list[GitCall] = []
    source = RepoSource(
        kind="github",
        original_ref="https://github.com/langchain-ai/langchain",
        requested_ref="abc123",
    )

    handle = resolve_repo_source(
        source,
        cache_root=tmp_path,
        git_runner=make_fake_git_runner(calls),
    )

    assert handle.local_path == tmp_path / "github.com__langchain-ai__langchain"
    assert handle.cache_key == "github.com__langchain-ai__langchain"
    assert handle.file_count == 1
    assert handle.clone_url == "https://github.com/langchain-ai/langchain.git"
    assert handle.checkout_ref == "abc123"
    assert handle.source.requested_ref == "abc123"


def test_invalid_github_url_raises() -> None:
    source = RepoSource(kind="github", original_ref="https://example.com/langchain-ai/langchain")

    with pytest.raises(ValueError, match="Unsupported GitHub repo URL"):
        resolve_repo_source(source)


def create_cache_dir(cache_root: Path, name: str, size: int, mtime: float) -> Path:
    path = cache_root / name
    path.mkdir()
    (path / "repo.txt").write_bytes(b"x" * size)
    os.utime(path, (mtime, mtime))
    return path


def test_plan_cache_cleanup_missing_root_returns_empty(tmp_path: Path) -> None:
    plan = plan_cache_cleanup(tmp_path / "missing", CachePolicy(max_repos=1, max_bytes=10))

    assert plan.total_repos == 0
    assert plan.total_bytes == 0
    assert plan.entries_to_remove == []


def test_plan_cache_cleanup_removes_oldest_when_repo_limit_exceeded(tmp_path: Path) -> None:
    create_cache_dir(tmp_path, "old-repo", 5, 100)
    create_cache_dir(tmp_path, "new-repo", 5, 200)

    plan = plan_cache_cleanup(tmp_path, CachePolicy(max_repos=1, max_bytes=100))

    assert [entry.cache_key for entry in plan.entries_to_remove] == ["old-repo"]


def test_plan_cache_cleanup_removes_until_byte_limit_is_met(tmp_path: Path) -> None:
    create_cache_dir(tmp_path, "old-repo", 8, 100)
    create_cache_dir(tmp_path, "new-repo", 8, 200)

    plan = plan_cache_cleanup(tmp_path, CachePolicy(max_repos=10, max_bytes=10))

    assert [entry.cache_key for entry in plan.entries_to_remove] == ["old-repo"]


def test_assess_repo_size_allows_small_repo(tmp_path: Path) -> None:
    handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
        file_count=10,
    )

    assessment = assess_repo_size(handle, RepoSizePolicy(max_files=100, sampling_limit=20))

    assert assessment.is_oversized is False
    assert assessment.sampling_proposal is None


def test_assess_repo_size_proposes_sampling_for_large_repo(tmp_path: Path) -> None:
    handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
        file_count=101,
    )

    assessment = assess_repo_size(handle, RepoSizePolicy(max_files=100, sampling_limit=20))

    assert assessment.is_oversized is True
    assert assessment.sampling_proposal is not None
    assert assessment.sampling_proposal.sampling_limit == 20
    assert assessment.sampling_proposal.requires_confirmation is True


def test_assess_repo_size_skips_unknown_file_count(tmp_path: Path) -> None:
    handle = RepoHandle(
        source=RepoSource(kind="github", original_ref="https://github.com/langchain-ai/langchain"),
        local_path=tmp_path,
        file_count=None,
    )

    assessment = assess_repo_size(handle)

    assert assessment.file_count is None
    assert assessment.is_oversized is False
    assert assessment.sampling_proposal is None


GitCall = tuple[list[str], Path | None]


def make_fake_git_runner(calls: list[GitCall]) -> Callable[[list[str], Path | None], None]:
    def fake_git_runner(args: list[str], cwd: Path | None = None) -> None:
        calls.append((args, cwd))
        if args[:4] == ["git", "clone", "--depth", "1"]:
            target = Path(args[-1])
            (target / ".git").mkdir(parents=True)
            (target / "README.md").write_text("# repo\n")

    return fake_git_runner


def test_resolve_github_repo_clones_missing_cache(tmp_path: Path) -> None:
    calls: list[GitCall] = []
    source = RepoSource(kind="github", original_ref="https://github.com/langchain-ai/langchain")

    handle = resolve_repo_source(
        source,
        cache_root=tmp_path,
        git_runner=make_fake_git_runner(calls),
    )

    expected_path = tmp_path / "github.com__langchain-ai__langchain"
    assert handle.local_path == expected_path
    assert handle.cache_key == "github.com__langchain-ai__langchain"
    assert handle.clone_url == "https://github.com/langchain-ai/langchain.git"
    assert handle.file_count == 1
    assert calls == [
        (
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/langchain-ai/langchain.git",
                str(expected_path),
            ],
            None,
        )
    ]


def test_resolve_github_repo_fetches_and_checkouts_requested_ref(tmp_path: Path) -> None:
    calls: list[GitCall] = []
    source = RepoSource(
        kind="github",
        original_ref="https://github.com/langchain-ai/langchain",
        requested_ref="abc123",
    )

    handle = resolve_repo_source(
        source,
        cache_root=tmp_path,
        git_runner=make_fake_git_runner(calls),
    )

    assert handle.checkout_ref == "abc123"
    assert calls[1:] == [
        (["git", "fetch", "--depth", "1", "origin", "abc123"], handle.local_path),
        (["git", "checkout", "--detach", "FETCH_HEAD"], handle.local_path),
    ]


def test_resolve_github_repo_reuses_existing_cache(tmp_path: Path) -> None:
    local_path = tmp_path / "github.com__langchain-ai__langchain"
    (local_path / ".git").mkdir(parents=True)
    (local_path / "README.md").write_text("# cached\n")
    calls: list[GitCall] = []

    handle = resolve_repo_source(
        RepoSource(kind="github", original_ref="https://github.com/langchain-ai/langchain"),
        cache_root=tmp_path,
        git_runner=make_fake_git_runner(calls),
    )

    assert handle.local_path == local_path
    assert handle.file_count == 1
    assert calls == []


def test_resolve_github_repo_rejects_non_git_cache_path(tmp_path: Path) -> None:
    local_path = tmp_path / "github.com__langchain-ai__langchain"
    local_path.mkdir()

    with pytest.raises(ValueError, match="not a git repo"):
        resolve_repo_source(
            RepoSource(kind="github", original_ref="https://github.com/langchain-ai/langchain"),
            cache_root=tmp_path,
            git_runner=make_fake_git_runner([]),
        )
