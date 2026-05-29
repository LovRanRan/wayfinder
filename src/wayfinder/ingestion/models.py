"""Repo ingestion data models."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

RepoKind = Literal["local", "github"]


class RepoSource(BaseModel):
    kind: RepoKind
    original_ref: str
    requested_ref: str | None = None


class RepoHandle(BaseModel):
    source: RepoSource
    local_path: Path
    cache_key: str | None = None
    clone_url: str | None = None
    checkout_ref: str | None = None
    file_count: int | None = None


class GitHubRepoRef(BaseModel):
    owner: str
    repo: str
    clone_url: str
    cache_key: str
    requested_ref: str | None = None


class CachePolicy(BaseModel):
    max_repos: int = Field(default=20, ge=1)
    max_bytes: int = Field(default=5 * 1024 * 1024 * 1024, ge=0)


class CacheEntry(BaseModel):
    cache_key: str
    path: Path
    size_bytes: int
    last_used_at: float


class CacheCleanupPlan(BaseModel):
    cache_root: Path
    total_repos: int
    total_bytes: int
    entries_to_remove: list[CacheEntry]


class RepoSizePolicy(BaseModel):
    max_files: int = Field(default=10000, ge=1)
    sampling_limit: int = Field(default=1000, ge=1)


class RepoSamplingProposal(BaseModel):
    reason: str
    sampling_limit: int
    requires_confirmation: bool = True


class RepoSizeAssessment(BaseModel):
    file_count: int | None
    max_files: int
    is_oversized: bool
    sampling_proposal: RepoSamplingProposal | None = None