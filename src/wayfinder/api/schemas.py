"""API request and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "running", "completed", "failed"]
TraceMetadataValue = str | int | float | bool | None
RuntimeLLMRouting = Literal["off", "openai"]
RuntimeFinalWriter = Literal["deterministic", "openai"]
SandboxStatus = Literal["disabled", "unavailable", "enabled"]


class ExplainRequest(BaseModel):
    repo_url: str = Field(min_length=1)
    query: str = Field(min_length=1)


class RefineRequest(BaseModel):
    correction: str = Field(min_length=1)


class AuthRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8)
    display_name: str | None = Field(default=None, max_length=80)


class UserProfile(BaseModel):
    user_id: str
    workspace_id: str
    display_name: str


class AuthResponse(BaseModel):
    user: UserProfile
    token: str


class WorkspaceRuntimeSettings(BaseModel):
    openai_api_key_encrypted: str | None = None
    openai_api_key_label: str | None = None
    openai_model: str | None = Field(default=None, min_length=1, max_length=80)
    llm_routing: RuntimeLLMRouting | None = None
    final_writer: RuntimeFinalWriter | None = None


class WorkspaceSettingsRequest(BaseModel):
    openai_api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    clear_openai_api_key: bool = False
    openai_model: str | None = Field(default=None, min_length=1, max_length=80)
    llm_routing: RuntimeLLMRouting | None = None
    final_writer: RuntimeFinalWriter | None = None


class WorkspaceSettingsResponse(BaseModel):
    workspace_id: str
    display_name: str
    openai_key_configured: bool
    openai_key_label: str | None = None
    openai_model: str
    llm_routing: RuntimeLLMRouting
    final_writer: RuntimeFinalWriter
    verifier_runner: str
    sandbox_status: SandboxStatus
    sandbox_message: str


class RunError(BaseModel):
    node: str
    error_type: str
    message: str
    retryable: bool = False


class RunSummary(BaseModel):
    job_id: str
    user_id: str = "local-dev"
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
