"""API request and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "running", "completed", "failed"]
ThreadStatus = Literal["active", "running", "failed", "archived"]
ThreadMessageRole = Literal["user", "assistant", "system"]
TraceMetadataValue = str | int | float | bool | None
RuntimeLLMRouting = Literal["off", "openai"]
RuntimeFinalWriter = Literal["deterministic", "openai"]
SandboxStatus = Literal["disabled", "unavailable", "enabled"]
AnswerMode = Literal["auto", "conversation", "report", "evidence", "clarify"]
ChatIntent = Literal[
    "chat_only",
    "repo_question",
    "context_switch",
    "structured_report",
    "evidence_request",
    "clarification",
    "unsupported_action",
]
AgentTraceRole = Literal[
    "conversation_memory_agent",
    "supervisor_agent",
    "repo_cartographer_agent",
    "symbol_investigator_agent",
    "verification_agent",
    "final_synthesizer_agent",
    "external_context_scout",
]


class ExplainRequest(BaseModel):
    repo_url: str = Field(min_length=1)
    query: str = Field(min_length=1)


class RefineRequest(BaseModel):
    correction: str = Field(min_length=1)


class ThreadCreateRequest(BaseModel):
    repo_url: str = Field(min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    initial_query: str | None = Field(default=None, min_length=1)


class ThreadMessageRequest(BaseModel):
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    content: str = Field(min_length=1)
    thread_id: str | None = Field(default=None, min_length=1)
    repo_url: str | None = Field(default=None, min_length=1)
    answer_mode: AnswerMode = "auto"


class WorkspaceContextRequest(BaseModel):
    thread_id: str | None = Field(default=None, min_length=1)
    repo_url: str | None = Field(default=None, min_length=1)


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
    # Classified routing intent (architectural / runtime / behavioral / debug /
    # mixed). Surfaced so external eval harnesses can score routing accuracy.
    # Persisted in run_json; old rows without it fall back to None.
    intent: str | None = None
    final_output: str | None = None
    error: str | None = None
    partial_summaries: dict[str, str] = Field(default_factory=dict)
    errors: list[RunError] = Field(default_factory=list)
    user_corrections: list[str] = Field(default_factory=list)
    verified_count: int = 0
    unverified_count: int = 0
    contradicted_count: int = 0
    # Per-agent claim provenance from the multi-agent run (Commit 23). Persisted
    # inside run_json, so old rows without it fall back to an empty list.
    claim_provenance: list[dict[str, object]] = Field(default_factory=list)
    trace_url: str | None = None
    trace_metadata: dict[str, TraceMetadataValue] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ThreadMessage(BaseModel):
    message_id: str
    thread_id: str
    role: ThreadMessageRole
    content: str
    created_at: datetime
    source_run_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    verified_count: int = 0
    unverified_count: int = 0
    contradicted_count: int = 0
    trace_metadata: dict[str, TraceMetadataValue] = Field(default_factory=dict)


class ConversationThread(BaseModel):
    thread_id: str
    user_id: str
    repo_url: str
    repo_name: str
    title: str
    status: ThreadStatus
    created_at: datetime
    updated_at: datetime
    last_run_id: str | None = None
    summary_memory: str | None = None


class ConversationThreadDetail(BaseModel):
    thread: ConversationThread
    messages: list[ThreadMessage] = Field(default_factory=list)
    runs: list[RunSummary] = Field(default_factory=list)
    active_run: RunSummary | None = None


class ActiveRepoContext(BaseModel):
    context_id: str
    user_id: str
    repo_url: str | None = None
    repo_name: str | None = None
    default_thread_id: str | None = None
    last_run_id: str | None = None
    status: Literal["empty", "ready", "running", "failed"] = "empty"
    summary_memory: str | None = None
    active_focus: str | None = None
    selected_files: list[str] = Field(default_factory=list)
    selected_symbols: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    updated_at: datetime


class ChatRouteDecision(BaseModel):
    intent: ChatIntent
    answer_mode: AnswerMode
    requires_grounded_run: bool = False
    requires_context_switch: bool = False
    clarification_question: str | None = None
    active_focus: str | None = None
    reason: str


class AgentTraceStep(BaseModel):
    agent_name: AgentTraceRole
    task: str
    status: Literal["planned", "queued", "completed", "skipped"]
    evidence_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AgentTraceAttachment(BaseModel):
    route: ChatRouteDecision
    steps: list[AgentTraceStep] = Field(default_factory=list)
    tool_refs: list[str] = Field(default_factory=list)
    verifier_status: str | None = None
    final_handoff: str | None = None


class ChatResponse(BaseModel):
    thread: ConversationThreadDetail | None = None
    active_context: ActiveRepoContext
    active_run: RunSummary | None = None
    route: ChatRouteDecision
    agent_trace: AgentTraceAttachment
