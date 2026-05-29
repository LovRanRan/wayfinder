"""API request and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "running", "completed", "failed"]


class ExplainRequest(BaseModel):
    repo_url: str = Field(min_length=1)
    query: str = Field(min_length=1)


class RefineRequest(BaseModel):
    correction: str = Field(min_length=1)


class RunSummary(BaseModel):
    job_id: str
    repo_url: str
    query: str
    status: RunStatus
    current_node: str | None = None
    final_output: str | None = None
    error: str | None = None
    verified_count: int = 0
    unverified_count: int = 0
    contradicted_count: int = 0
    trace_url: str | None = None
    created_at: datetime
    updated_at: datetime
