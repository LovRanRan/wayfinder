"""Schemas shared by the sandbox worker and remote verifier adapter."""

from typing import Literal

from pydantic import BaseModel, Field

SandboxFramework = Literal["pytest", "jest"]
SandboxToolName = Literal["run_single_test", "run_pytest", "run_jest"]
SandboxObservationStatus = Literal["passed", "failed", "timed_out", "malformed", "tool_error"]


class SandboxHealthResult(BaseModel):
    status: Literal["ok", "error"]
    service: str = "wayfinder-test-sandbox"
    message: str | None = None


class SandboxTestRequest(BaseModel):
    test_ref: str = Field(min_length=1, max_length=128)
    claim_refs: list[str] = Field(default_factory=list)
    framework: SandboxFramework
    tool_name: SandboxToolName
    path: str = Field(min_length=1, max_length=4096)
    test_filter: str = Field(min_length=1, max_length=512)
    timeout_seconds: float = Field(gt=0, le=120)
    max_output_bytes: int = Field(default=12000, ge=256, le=64000)
    job_id: str | None = Field(default=None, max_length=128)
    run_owner: str | None = Field(default=None, max_length=128)
    repo_url: str | None = Field(default=None, max_length=4096)


class SandboxTestObservation(BaseModel):
    test_ref: str
    status: SandboxObservationStatus
    output: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[str] = Field(default_factory=list)
    cleanup_done: bool = True
    denied_reason: str | None = None
