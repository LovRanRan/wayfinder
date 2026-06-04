"""API request and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "running", "completed", "failed"]
TraceMetadataValue = str | int | float | bool | None


class ExplainRequest(BaseModel):
    repo_url: str = Field(min_length=1)
    query: str = Field(min_length=1)


class RefineRequest(BaseModel):
    correction: str = Field(min_length=1)


class RunError(BaseModel):
    node: str
    error_type: str
    message: str
    retryable: bool = False


class RunSummary(BaseModel):
    job_id: str
    repo_url: str
    query: str
    status: RunStatus
    current_node: str | None = None
    final_output: str | None = None
    error: str | None = None
    partial_summaries: dict[str, str] = Field(default_factory=dict)
    errors: list[RunError] = Field(default_factory=list)
    user_corrections: list[str] = Field(default_factory=list)
    verified_count: int = 0
    unverified_count: int = 0
    contradicted_count: int = 0
    trace_url: str | None = None
    trace_metadata: dict[str, TraceMetadataValue] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
