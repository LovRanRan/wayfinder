"""Tests for module-source grounding (design note 025)."""

from pathlib import Path

from wayfinder.graph.entry import module_symbol_candidate_from_state
from wayfinder.graph.module_source import (
    find_module_file,
    module_symbol_candidate,
    outline_module_source,
    select_symbol,
)
from wayfinder.ingestion.models import RepoHandle, RepoSource

_GEOIP_SOURCE = '''\
"""Geo helpers."""

import socket


def resolve_proxy_geo(proxy_url: str) -> tuple[str | None, str | None]:
    """Resolve timezone and locale from a proxy's IP address."""
    return None, None


def _resolve_proxy_ip(proxy_url: str) -> str | None:
    return None


class GeoCache:
    """In-memory cache."""

    def get(self, key: str) -> str | None:
        return None
'''


def _write_repo(tmp_path: Path) -> Path:
    pkg = tmp_path / "cloakbrowser"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "geoip.py").write_text(_GEOIP_SOURCE, encoding="utf-8")
    return tmp_path


def test_outline_extracts_functions_classes_with_lines() -> None:
    definitions = outline_module_source(_GEOIP_SOURCE)
    by_name = {item.name: item for item in definitions}

    assert set(by_name) == {"resolve_proxy_geo", "_resolve_proxy_ip", "GeoCache"}
    assert by_name["resolve_proxy_geo"].kind == "function"
    assert by_name["resolve_proxy_geo"].public is True
    assert by_name["resolve_proxy_geo"].lineno == 6
    assert "proxy_url: str" in (by_name["resolve_proxy_geo"].signature or "")
    assert by_name["resolve_proxy_geo"].doc == (
        "Resolve timezone and locale from a proxy's IP address."
    )
    assert by_name["_resolve_proxy_ip"].public is False
    assert by_name["GeoCache"].kind == "class"


def test_outline_ignores_nested_definitions() -> None:
    source = "def outer():\n    def inner():\n        return 1\n    return inner\n"
    names = [item.name for item in outline_module_source(source)]

    assert names == ["outer"]


def test_select_symbol_prefers_query_token_match() -> None:
    definitions = outline_module_source(_GEOIP_SOURCE)

    assert select_symbol(definitions, ["cache"]) == "GeoCache"


def test_select_symbol_falls_back_to_first_public_function() -> None:
    definitions = outline_module_source(_GEOIP_SOURCE)

    assert select_symbol(definitions, ["unrelated"]) == "resolve_proxy_geo"


def test_select_symbol_empty_returns_none() -> None:
    assert select_symbol([], ["anything"]) is None


def test_find_module_file_matches_bare_stem(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    found = find_module_file(str(tmp_path), "what does geoip do?")

    assert found is not None
    assert found.name == "geoip.py"


def test_find_module_file_matches_dotted_module(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    found = find_module_file(str(tmp_path), "explain cloakbrowser.geoip")

    assert found is not None
    assert found.name == "geoip.py"


def test_find_module_file_returns_none_for_repo_level_query(tmp_path: Path) -> None:
    _write_repo(tmp_path)

    assert find_module_file(str(tmp_path), "what does this repo do?") is None


def test_find_module_file_ambiguous_stem_prefers_shallowest(tmp_path: Path) -> None:
    pkg = tmp_path / "cloakbrowser"
    (pkg / "human").mkdir(parents=True)
    (pkg / "config.py").write_text("X = 1\n", encoding="utf-8")
    (pkg / "human" / "config.py").write_text("Y = 2\n", encoding="utf-8")

    found = find_module_file(str(tmp_path), "explain the config")

    assert found is not None
    assert found.relative_to(tmp_path) == Path("cloakbrowser/config.py")


def test_module_symbol_candidate_end_to_end(tmp_path: Path) -> None:
    _write_repo(tmp_path)

    assert (
        module_symbol_candidate(str(tmp_path), "what does geoip do?")
        == "resolve_proxy_geo"
    )


def test_module_symbol_candidate_no_module_returns_none(tmp_path: Path) -> None:
    _write_repo(tmp_path)

    assert module_symbol_candidate(str(tmp_path), "what does this repo do?") is None


def test_module_symbol_candidate_from_state(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    repo_handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )

    result = module_symbol_candidate_from_state(
        {"query": "what does geoip do?", "repo_handle": repo_handle}
    )

    assert result == "resolve_proxy_geo"
