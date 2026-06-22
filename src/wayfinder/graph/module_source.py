"""Module-source grounding for behavioural / architectural questions.

Design note 025. The entry_explainer used to dead-end on questions that name a
*module* but no *symbol* — e.g. "what does geoip do?", "explain the browser
module". `symbol_candidate_from_state` returned ``None`` (no code symbol, not a
CLI query) and the node returned ``entry_explainer_missing_symbol_candidate``,
so behavioural questions produced no grounded evidence and verified 0.

This module adds a deterministic fallback: when the query names a module that
exists in the repo, read that module's real source, parse it with the stdlib
``ast``, and pick the most relevant *real* public symbol. That symbol is then
fed through the existing AST/verifier path, so a behavioural question reaches
the same grounded evidence pipeline a precise symbol question already does —
no new graph node, schema, or routing change.

Scope boundary (deferred to a Haichuan-owned slice): emitting a *multi-symbol*
module outline as its own claim set with per-symbol verification lives in the
design note, not here. This file only resolves a single best symbol.
"""

import ast
import re
from pathlib import Path

_NOISE_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".tox",
        ".idea",
        ".eggs",
    }
)

# Words that are never a useful module target even if a same-named file exists.
_TOKEN_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "what",
        "does",
        "how",
        "this",
        "that",
        "with",
        "from",
        "into",
        "repo",
        "code",
        "file",
        "module",
        "package",
        "function",
        "method",
        "class",
        "explain",
        "describe",
        "show",
        "tell",
        "give",
        "about",
        "work",
        "works",
        "used",
        "use",
        "main",
        "init",
        "test",
        "tests",
    }
)

_BARE_TOKEN_PATTERN = re.compile(r"[A-Za-z_]\w+")
_DOTTED_MODULE_PATTERN = re.compile(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\b")

# Cap the repo walk so a pathological tree can't stall the node.
_MAX_PY_FILES = 5000


class ModuleDefinition:
    """One top-level definition discovered in a module's source."""

    __slots__ = ("name", "kind", "lineno", "signature", "doc", "public")

    def __init__(
        self,
        *,
        name: str,
        kind: str,
        lineno: int,
        signature: str | None,
        doc: str | None,
        public: bool,
    ) -> None:
        self.name = name
        self.kind = kind
        self.lineno = lineno
        self.signature = signature
        self.doc = doc
        self.public = public


def module_symbol_candidate(repo_path: str, query: str) -> str | None:
    """Resolve a query that names a module to a real symbol in that module.

    Returns the bare symbol name (the note-023 AST resolver handles unique-leaf
    and dotted-suffix resolution) or ``None`` when no module/symbol is found.
    """
    module_file = find_module_file(repo_path, query)
    if module_file is None:
        return None
    try:
        source = module_file.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        definitions = outline_module_source(source)
    except (SyntaxError, ValueError):
        return None
    return select_symbol(definitions, _query_tokens(query))


def find_module_file(repo_path: str, query: str) -> Path | None:
    root = Path(repo_path)
    if not root.is_dir():
        return None

    py_files: list[Path] = []
    for path in root.rglob("*.py"):
        if _is_noise_path(path, root):
            continue
        py_files.append(path)
        if len(py_files) >= _MAX_PY_FILES:
            break

    # 1) Explicit dotted module in the query wins (e.g. "cloakbrowser.geoip").
    for module in _DOTTED_MODULE_PATTERN.findall(query):
        parts = tuple(module.lower().split("."))
        for path in py_files:
            rel_parts = tuple(p.lower() for p in path.relative_to(root).with_suffix("").parts)
            if len(parts) <= len(rel_parts) and rel_parts[-len(parts):] == parts:
                return path

    # 2) Bare token matched against file stems; unambiguous (or uniquely
    #    shallowest) match only, otherwise stay honest and return None.
    for token in _query_tokens(query):
        matches = [
            path
            for path in py_files
            if path.stem.lower() == token and path.stem != "__init__"
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            ranked = sorted(matches, key=lambda p: len(p.relative_to(root).parts))
            if len(ranked[0].relative_to(root).parts) < len(ranked[1].relative_to(root).parts):
                return ranked[0]
            return None
    return None


def outline_module_source(source: str) -> list[ModuleDefinition]:
    """Top-level functions and classes of a module, with real line numbers."""
    tree = ast.parse(source)
    definitions: list[ModuleDefinition] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.append(_function_definition(node))
        elif isinstance(node, ast.ClassDef):
            definitions.append(_class_definition(node))
    return definitions


def select_symbol(
    definitions: list[ModuleDefinition], query_tokens: list[str]
) -> str | None:
    if not definitions:
        return None
    public = [item for item in definitions if item.public]
    pool = public or definitions

    # Prefer a definition whose name overlaps a query token.
    for token in query_tokens:
        for item in pool:
            if token in item.name.lower():
                return item.name

    # Otherwise the first public function, then class, then anything.
    for kind in ("function", "class"):
        for item in pool:
            if item.kind == kind:
                return item.name
    return pool[0].name


def _function_definition(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> ModuleDefinition:
    return ModuleDefinition(
        name=node.name,
        kind="function",
        lineno=node.lineno,
        signature=_signature(node),
        doc=_docstring_summary(node),
        public=not node.name.startswith("_"),
    )


def _class_definition(node: ast.ClassDef) -> ModuleDefinition:
    return ModuleDefinition(
        name=node.name,
        kind="class",
        lineno=node.lineno,
        signature=None,
        doc=_docstring_summary(node),
        public=not node.name.startswith("_"),
    )


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    try:
        params = ast.unparse(node.args)
    except Exception:  # pragma: no cover - defensive against odd AST nodes
        params = ", ".join(arg.arg for arg in node.args.args)
    returns = ""
    if node.returns is not None:
        try:
            returns = f" -> {ast.unparse(node.returns)}"
        except Exception:  # pragma: no cover
            returns = ""
    return f"{node.name}({params}){returns}"


def _docstring_summary(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> str | None:
    doc = ast.get_docstring(node)
    if not doc:
        return None
    return doc.strip().splitlines()[0].strip() or None


def _query_tokens(query: str) -> list[str]:
    seen: dict[str, None] = {}
    for token in _BARE_TOKEN_PATTERN.findall(query):
        lowered = token.lower()
        if lowered in _TOKEN_STOPWORDS or len(lowered) < 3:
            continue
        seen.setdefault(lowered, None)
    # Longer, more specific tokens first.
    return sorted(seen, key=len, reverse=True)


def _is_noise_path(path: Path, root: Path) -> bool:
    return any(part in _NOISE_DIRS for part in path.relative_to(root).parts)
