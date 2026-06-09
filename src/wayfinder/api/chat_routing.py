"""Deterministic routing for the product-level chat facade."""

from __future__ import annotations

import re

from wayfinder.api.schemas import ActiveRepoContext, ChatRequest, ChatRouteDecision

_GITHUB_URL_RE = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?")
_OWNER_REPO_RE = re.compile(r"\b[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\b")
_SYMBOL_RE = re.compile(r"\b[a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*){2,}\b")
_FILE_RE = re.compile(r"\b[\w./-]+\.(?:py|ts|tsx|js|jsx|md|json|toml|yaml|yml)\b")

_CODE_KEYWORDS = (
    "architecture",
    "architectural",
    "module",
    "entry",
    "entrypoint",
    "function",
    "class",
    "symbol",
    "file",
    "test",
    "tests",
    "behavior",
    "behaviour",
    "data flow",
    "call chain",
    "runtime",
    "code",
    "implementation",
    "where should",
    "what files",
)
_REPORT_KEYWORDS = ("structured report", "report version", "structured answer")
_EVIDENCE_KEYWORDS = ("evidence", "prove", "verified", "verification", "trace")
_MEMORY_KEYWORDS = ("summarize", "summary", "what did we learn", "what we learned")
_UNSUPPORTED_KEYWORDS = (
    "edit code",
    "modify code",
    "write code",
    "run command",
    "shell",
    "private repo",
)


def decide_chat_route(request: ChatRequest, context: ActiveRepoContext) -> ChatRouteDecision:
    """Return a deterministic product route for a natural chat message."""

    content = request.content.strip()
    lowered = content.lower()
    explicit_focus = extract_focus(content)
    repo_ref = extract_repo_ref(content) or request.repo_url
    has_repo = context.repo_url is not None
    wants_report = request.answer_mode == "report" or any(
        key in lowered for key in _REPORT_KEYWORDS
    )
    wants_evidence = request.answer_mode == "evidence" or any(
        key in lowered for key in _EVIDENCE_KEYWORDS
    )
    asks_code = _asks_about_code(lowered, explicit_focus=explicit_focus)

    if any(key in lowered for key in _UNSUPPORTED_KEYWORDS):
        return ChatRouteDecision(
            intent="unsupported_action",
            answer_mode="conversation",
            requires_grounded_run=False,
            active_focus=explicit_focus or context.active_focus,
            reason="message asks for an unsupported editing, shell, or private-resource action",
        )

    if repo_ref is not None:
        return ChatRouteDecision(
            intent="context_switch",
            answer_mode="report" if asks_code or wants_report else "conversation",
            requires_grounded_run=asks_code or wants_report or "understand" in lowered,
            requires_context_switch=True,
            active_focus=explicit_focus,
            reason="message includes a repository reference",
        )

    if not has_repo and asks_code:
        return ChatRouteDecision(
            intent="clarification",
            answer_mode="clarify",
            requires_grounded_run=False,
            clarification_question="Which public GitHub repo should I use for this code question?",
            reason="code question has no active repo context",
        )

    if any(key in lowered for key in _MEMORY_KEYWORDS) and not asks_code:
        return ChatRouteDecision(
            intent="chat_only",
            answer_mode="conversation",
            requires_grounded_run=False,
            active_focus=context.active_focus,
            reason="message asks to summarize prior conversation memory",
        )

    if wants_evidence:
        return ChatRouteDecision(
            intent="evidence_request",
            answer_mode="evidence",
            requires_grounded_run=has_repo,
            active_focus=explicit_focus or context.active_focus,
            reason="message asks for evidence or verification details",
        )

    if wants_report:
        return ChatRouteDecision(
            intent="structured_report",
            answer_mode="report",
            requires_grounded_run=has_repo,
            active_focus=explicit_focus or context.active_focus,
            reason="message asks for a structured grounded report",
        )

    if asks_code and has_repo:
        return ChatRouteDecision(
            intent="repo_question",
            answer_mode="report" if request.answer_mode == "auto" else request.answer_mode,
            requires_grounded_run=True,
            active_focus=explicit_focus or context.active_focus,
            reason="message asks for codebase facts in the active repo context",
        )

    return ChatRouteDecision(
        intent="chat_only",
        answer_mode="conversation" if request.answer_mode == "auto" else request.answer_mode,
        requires_grounded_run=False,
        active_focus=context.active_focus,
        reason="message can be answered conversationally without new code facts",
    )


def extract_repo_ref(content: str) -> str | None:
    github_match = _GITHUB_URL_RE.search(content)
    if github_match is not None:
        return github_match.group(0).rstrip("/")

    owner_repo_match = _OWNER_REPO_RE.search(content)
    if owner_repo_match is None:
        return None
    value = owner_repo_match.group(0)
    if "." in value.rsplit("/", maxsplit=1)[-1]:
        return None
    return f"https://github.com/{value}"


def extract_focus(content: str) -> str | None:
    file_match = _FILE_RE.search(content)
    if file_match is not None:
        return file_match.group(0)

    symbol_match = _SYMBOL_RE.search(content)
    if symbol_match is not None:
        return symbol_match.group(0)

    return None


def _asks_about_code(lowered: str, *, explicit_focus: str | None) -> bool:
    return explicit_focus is not None or any(keyword in lowered for keyword in _CODE_KEYWORDS)
