"""Entry-explainer AST evidence helpers."""

import asyncio
import re
from typing import Protocol, cast

from wayfinder.graph.state import WayfinderState
from wayfinder.mcp.adapter import MCPToolCallError
from wayfinder.mcp.models import MCPToolCall, MCPToolCallResult

_EXPLICIT_SYMBOL_PATTERN = re.compile(r"\b[A-Za-z_]\w*(?:[.:][A-Za-z_]\w*)+\b")


class _PlaceholderEntryScanner:
    def explain_symbol(self, repo_path: str, symbol: str) -> dict[str, object]:
        return {
            "symbol": symbol,
            "repo_path": repo_path,
            "definition": None,
            "signature": None,
            "references": [],
            "call_chain": [],
            "limitations": [
                "Placeholder entry scanner: real mcp-ast-explorer evidence is not wired yet."
            ],
        }


class EntryScanner(Protocol):
    def explain_symbol(self, repo_path: str, symbol: str) -> dict[str, object]: ...


class _MCPAdapter(Protocol):
    async def call_tool(self, call: MCPToolCall) -> MCPToolCallResult: ...


class MCPEntryScanner:
    def __init__(self, adapter: _MCPAdapter) -> None:
        self._adapter = adapter

    def explain_symbol(self, repo_path: str, symbol: str) -> dict[str, object]:
        try:
            definition = self._call_dict(
                MCPToolCall(
                    tool_name="find_definition",
                    arguments={"path": repo_path, "symbol": symbol, "language": "python"},
                )
            )
        except MCPToolCallError as exc:
            return _tool_error_evidence(
                symbol=symbol,
                message=exc.error.message,
                retryable=exc.error.retryable,
            )

        if not _tool_result_found(definition):
            return _missing_symbol_evidence(symbol=symbol, definition=definition)

        try:
            signature: dict[str, object] | None = None
            class_hierarchy: dict[str, object] | None = None
            if _definition_kind(definition) != "class":
                signature = self._call_dict(
                    MCPToolCall(
                        tool_name="function_signature",
                        arguments={
                            "path": repo_path,
                            "symbol": symbol,
                            "language": "python",
                        },
                    )
                )
            references = self._call_dict(
                MCPToolCall(
                    tool_name="find_references",
                    arguments={"path": repo_path, "symbol": symbol, "language": "python"},
                )
            )
            call_chain = self._call_dict(
                MCPToolCall(
                    tool_name="call_chain",
                    arguments={
                        "path": repo_path,
                        "from_symbol": symbol,
                        "depth": 2,
                        "language": "python",
                    },
                )
            )
            if _definition_kind(definition) == "class":
                class_hierarchy = self._call_dict(
                    MCPToolCall(
                        tool_name="class_hierarchy",
                        arguments={
                            "path": repo_path,
                            "class_name": symbol,
                            "language": "python",
                        },
                    )
                )
        except MCPToolCallError as exc:
            return _tool_error_evidence(
                symbol=symbol,
                message=exc.error.message,
                retryable=exc.error.retryable,
                definition=definition,
            )

        return {
            "status": "found",
            "symbol": str(definition.get("symbol", symbol)),
            "definition": definition,
            "signature": signature,
            "references": references,
            "call_chain": call_chain,
            "class_hierarchy": class_hierarchy,
            "limitations": [],
        }

    def _call_dict(self, call: MCPToolCall) -> dict[str, object]:
        result = self._call_adapter(call)
        content: object = result.content

        if not isinstance(content, dict):
            raise TypeError(
                f"mcp-ast-explorer {call.tool_name} returned non-dict content"
            )

        return cast(dict[str, object], content)

    def _call_adapter(self, call: MCPToolCall) -> MCPToolCallResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._adapter.call_tool(call))

        raise RuntimeError("MCP entry scanner cannot run inside an active event loop")


def repo_path_from_state(state: WayfinderState) -> str | None:
    repo_handle = state.get("repo_handle")
    if repo_handle is None:
        return None

    return str(repo_handle.local_path)


def symbol_candidate_from_state(state: WayfinderState) -> str | None:
    query_symbol = _symbol_candidate_from_query(state.get("query", ""))
    if query_symbol is not None:
        return query_symbol

    entry_points = state.get("entry_points")
    if not entry_points:
        return None

    return entry_points[0]


def entry_explainer_missing_repo_path() -> WayfinderState:
    return {
        "errors": [
            {
                "node": "entry_explainer",
                "error_type": "missing_repo_path",
                "message": "entry_explainer requires a local repo path from ingestion.",
                "retryable": False,
            }
        ],
        "partial_summaries": {
            "entry_explainer": (
                "Entry explanation unavailable: I cannot inspect AST evidence "
                "because no local repo path was available from ingestion."
            )
        },
        "next_agent": "final_writer",
    }


def entry_explainer_missing_symbol_candidate() -> WayfinderState:
    return {
        "errors": [
            {
                "node": "entry_explainer",
                "error_type": "missing_symbol_candidate",
                "message": (
                    "entry_explainer requires an explicit symbol or an entry point "
                    "candidate from architect_mapper."
                ),
                "retryable": False,
            }
        ],
        "partial_summaries": {
            "entry_explainer": (
                "Entry explanation unavailable: I cannot inspect AST evidence "
                "because no symbol candidate was available from the user query "
                "or architect_mapper entry points."
            )
        },
        "next_agent": "final_writer",
    }


def entry_state_from_ast_result(ast_result: object) -> WayfinderState:
    if not isinstance(ast_result, dict):
        raise TypeError("entry_explainer requires dict AST result")

    ast_index = cast(dict[str, object], ast_result)
    symbol = ast_index.get("symbol")
    symbol_text = str(symbol) if symbol is not None else "unknown symbol"
    status = ast_index.get("status")

    if status in ("missing", "unsupported", "tool_error"):
        error_type = _entry_error_type_from_ast_index(ast_index)
        return {
            "ast_index": ast_index,
            "errors": [
                {
                    "node": "entry_explainer",
                    "error_type": error_type,
                    "message": _degraded_error_message(ast_index, symbol_text=symbol_text),
                    "retryable": _is_retryable_tool_error(ast_index, status=status),
                }
            ],
            "partial_summaries": {
                "entry_explainer": _degraded_entry_summary(
                    ast_index,
                    symbol_text=symbol_text,
                )
            },
            "next_agent": "final_writer",
        }

    return {
        "ast_index": ast_index,
        "partial_summaries": {
            "entry_explainer": _entry_summary_from_ast_index(
                ast_index,
                symbol_text=symbol_text,
            )
        },
        "next_agent": "final_writer",
    }


def scan_symbol_for_entry(
    repo_path: str,
    symbol: str,
    *,
    scanner: EntryScanner | None = None,
) -> dict[str, object]:
    active_scanner = scanner or _PlaceholderEntryScanner()
    return active_scanner.explain_symbol(repo_path, symbol)


def _missing_symbol_evidence(
    *,
    symbol: str,
    definition: dict[str, object],
) -> dict[str, object]:
    error = definition.get("error")
    if _is_unsupported_language_error(error):
        status = "unsupported"
    elif _is_parse_error(error):
        status = "tool_error"
    else:
        status = "missing"
    limitation = str(error) if error is not None else f"Symbol not found: {symbol}"

    return {
        "status": status,
        "symbol": str(definition.get("symbol", symbol)),
        "definition": definition,
        "signature": None,
        "references": [],
        "call_chain": [],
        "class_hierarchy": None,
        "retryable": False,
        "limitations": [limitation],
    }


def _tool_error_evidence(
    *,
    symbol: str,
    message: str,
    retryable: bool,
    definition: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": "tool_error",
        "symbol": symbol,
        "definition": definition,
        "signature": None,
        "references": [],
        "call_chain": [],
        "class_hierarchy": None,
        "retryable": retryable,
        "limitations": [message],
    }


def _is_unsupported_language_error(error: object) -> bool:
    return isinstance(error, str) and "unsupported language" in error.lower()


def _is_parse_error(error: object) -> bool:
    if not isinstance(error, str):
        return False

    lowered = error.lower()
    return "parse error" in lowered or "syntax error" in lowered or "syntaxerror" in lowered


def _definition_kind(definition: dict[str, object]) -> str:
    kind = definition.get("kind")
    return str(kind).lower() if kind is not None else ""


def _tool_result_found(result: dict[str, object]) -> bool:
    found = result.get("found")
    return found if isinstance(found, bool) else False


def _entry_error_type_from_ast_index(ast_index: dict[str, object]) -> str:
    status = str(ast_index.get("status", "unknown"))
    if status == "missing":
        return "missing_symbol"
    if status == "unsupported":
        return "unsupported_language"
    if _limitations_include_parse_error(ast_index):
        return "ast_parse_error"
    return "ast_tool_error"


def _is_retryable_tool_error(ast_index: dict[str, object], *, status: object) -> bool:
    if status != "tool_error":
        return False

    retryable = ast_index.get("retryable")
    return retryable if isinstance(retryable, bool) else True


def _degraded_error_message(
    ast_index: dict[str, object],
    *,
    symbol_text: str,
) -> str:
    limitations = _limitations_from_ast_index(ast_index)
    if limitations:
        return limitations[0]

    return f"entry_explainer could not collect AST evidence for {symbol_text}."


def _degraded_entry_summary(
    ast_index: dict[str, object],
    *,
    symbol_text: str,
) -> str:
    status = str(ast_index.get("status", "unknown"))
    limitations = _limitations_from_ast_index(ast_index)
    limitation_text = limitations[0] if limitations else "no detailed limitation returned"

    if status == "missing":
        reason = f"symbol {symbol_text} was not found"
    elif status == "unsupported":
        reason = (
            "the repository or file language is unsupported; "
            "v1 only trusts python AST evidence"
        )
    elif _limitations_include_parse_error(ast_index):
        reason = "the Python AST parser could not parse the source"
    else:
        reason = "the AST evidence tool failed"

    return (
        f"Entry explanation degraded for {symbol_text}: {reason}. "
        f"Evidence limitation: {limitation_text}. "
        "No references or call chain are asserted without definition evidence."
    )


def _limitations_from_ast_index(ast_index: dict[str, object]) -> list[str]:
    limitations = ast_index.get("limitations")
    if not isinstance(limitations, list):
        return []

    return [str(item) for item in cast(list[object], limitations)]


def _limitations_include_parse_error(ast_index: dict[str, object]) -> bool:
    return any(_is_parse_error(item) for item in _limitations_from_ast_index(ast_index))


def _symbol_candidate_from_query(query: str) -> str | None:
    backtick_symbols: list[str] = [
        item.strip()
        for item in re.findall(r"`([^`]+)`", query)
        if _EXPLICIT_SYMBOL_PATTERN.fullmatch(item.strip())
    ]
    token_symbols: list[str] = _EXPLICIT_SYMBOL_PATTERN.findall(query)
    candidates: list[str] = list(dict.fromkeys([*backtick_symbols, *token_symbols]))

    if len(candidates) == 1:
        return candidates[0]

    return None


def _entry_summary_from_ast_index(
    ast_index: dict[str, object],
    *,
    symbol_text: str,
) -> str:
    definition_text = _definition_summary(ast_index.get("definition"))
    signature_text = _signature_summary(ast_index)
    reference_text, reference_citations = _references_summary(ast_index.get("references"))
    call_chain_text = _call_chain_summary(ast_index.get("call_chain"), symbol_text=symbol_text)
    class_hierarchy_text = _class_hierarchy_summary(ast_index.get("class_hierarchy"))
    citation_items = _source_citations(
        definition=ast_index.get("definition"),
        reference_citations=reference_citations,
    )
    limitations = _limitations_from_ast_index(ast_index)
    limitation_text = (
        "; ".join(limitations)
        if limitations
        else (
            "empty references or call_chain means no evidence was returned, "
            "not proof of unused code"
        )
    )

    parts = [
        f"Entry explanation evidence collected for {symbol_text}.",
        f"Definition: {definition_text}.",
        f"Signature: {signature_text}.",
        f"Call chain: {call_chain_text}.",
        f"References: {reference_text}.",
    ]

    if class_hierarchy_text is not None:
        parts.append(f"Class hierarchy: {class_hierarchy_text}.")

    parts.extend(
        [
            f"Key functions: {call_chain_text}.",
            (
                "Data flow evidence: "
                f"{call_chain_text}; reference sites show where the symbol is mentioned."
            ),
            f"Assumptions: {limitation_text}.",
            f"Source citations: {'; '.join(citation_items) if citation_items else 'none'}.",
        ]
    )

    return "\n".join(parts)


def _definition_summary(definition: object) -> str:
    if not isinstance(definition, dict):
        return "not available"

    definition_dict = cast(dict[str, object], definition)
    citation = _location_citation(definition_dict.get("location"))
    return citation or "definition evidence returned without a location"


def _signature_summary(ast_index: dict[str, object]) -> str:
    signature = ast_index.get("signature")
    if isinstance(signature, str):
        return signature

    if isinstance(signature, dict):
        signature_dict = cast(dict[str, object], signature)
        raw_signature = signature_dict.get("signature")
        if raw_signature is not None:
            return str(raw_signature)

    definition = ast_index.get("definition")
    if isinstance(definition, dict):
        definition_dict = cast(dict[str, object], definition)
        raw_signature = definition_dict.get("signature")
        if raw_signature is not None:
            return str(raw_signature)

    return "not available"


def _references_summary(references: object) -> tuple[str, list[str]]:
    reference_items: object = references
    if isinstance(references, dict):
        reference_items = cast(dict[str, object], references).get("references")

    if not isinstance(reference_items, list) or not reference_items:
        return "none returned", []

    citations: list[str] = []
    for item in cast(list[object], reference_items):
        if not isinstance(item, dict):
            continue
        item_dict = cast(dict[str, object], item)
        citation = (
            _location_citation(item_dict["location"])
            if "location" in item_dict
            else _location_citation(item_dict)
        )
        if citation is not None:
            citations.append(citation)

    if not citations:
        return "returned without source locations", []

    return ", ".join(citations), citations


def _call_chain_summary(call_chain: object, *, symbol_text: str) -> str:
    if isinstance(call_chain, dict):
        call_chain_dict = cast(dict[str, object], call_chain)
        callers = call_chain_dict.get("callers")
        if isinstance(callers, list) and callers:
            caller_symbols: list[str] = []
            for item in cast(list[object], callers):
                if not isinstance(item, dict):
                    continue
                item_dict = cast(dict[str, object], item)
                symbol = item_dict.get("symbol")
                if symbol is not None:
                    caller_symbols.append(str(symbol))
            if caller_symbols:
                return " -> ".join([", ".join(caller_symbols), symbol_text])

    if isinstance(call_chain, list) and call_chain:
        edges: list[str] = []
        for item in cast(list[object], call_chain):
            if not isinstance(item, dict):
                continue
            item_dict = cast(dict[str, object], item)
            caller = item_dict.get("caller")
            callee = item_dict.get("callee")
            if caller is not None and callee is not None:
                edges.append(f"{caller} -> {callee}")
        if edges:
            return "; ".join(edges)

    return "none returned"


def _class_hierarchy_summary(class_hierarchy: object) -> str | None:
    if class_hierarchy is None:
        return None

    if not isinstance(class_hierarchy, dict):
        return "returned in an unsupported shape"

    class_hierarchy_dict = cast(dict[str, object], class_hierarchy)
    subclasses = class_hierarchy_dict.get("subclasses")
    if not isinstance(subclasses, list) or not subclasses:
        return "no direct subclasses returned"

    names: list[str] = []
    for item in cast(list[object], subclasses):
        if not isinstance(item, dict):
            continue
        item_dict = cast(dict[str, object], item)
        class_name = item_dict.get("class_name")
        if class_name is not None:
            names.append(str(class_name))

    return ", ".join(names) if names else "subclasses returned without class names"


def _source_citations(
    *,
    definition: object,
    reference_citations: list[str],
) -> list[str]:
    citations: list[str] = []
    if isinstance(definition, dict):
        definition_dict = cast(dict[str, object], definition)
        definition_citation = _location_citation(definition_dict.get("location"))
        if definition_citation is not None:
            citations.append(definition_citation)

    for citation in reference_citations:
        if citation not in citations:
            citations.append(citation)

    return citations


def _location_citation(location: object) -> str | None:
    if not isinstance(location, dict):
        return None

    location_dict = cast(dict[str, object], location)
    path = location_dict.get("relative_path") or location_dict.get("path")
    line = location_dict.get("line")

    if path is None:
        return None

    if isinstance(line, int):
        return f"{path}:{line}"

    return str(path)
