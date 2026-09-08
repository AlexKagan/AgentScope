"""Static guard: provider/LangChain code stays behind the model boundary.

Design 11.6 / ADR 0012: ``langchain*`` and ``openai`` imports are limited to the
model implementation and bootstrap, and provider-response fields are parsed only
inside ``agentscope.models``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import agentscope

_SRC = Path(agentscope.__file__).parent

# Modules allowed to import a provider SDK / LangChain.
_PROVIDER_IMPORT_ALLOWED = {
    _SRC / "models" / "openai_compatible.py",
    _SRC / "bootstrap" / "clients.py",
}
_PROVIDER_ROOTS = {"langchain", "langchain_core", "langchain_openai", "langgraph", "openai"}

# Raw provider/LangChain response fields must only be read under models/.
_PROVIDER_RESPONSE_TOKENS = ("usage_metadata", "response_metadata")


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize(
    "path",
    sorted(p for p in _SRC.rglob("*.py")),
    ids=lambda p: str(p.relative_to(_SRC)),
)
def test_provider_sdk_imports_are_confined(path: Path) -> None:
    roots = _imported_roots(ast.parse(path.read_text(encoding="utf-8")))
    leaked = roots & _PROVIDER_ROOTS
    if leaked and path not in _PROVIDER_IMPORT_ALLOWED:
        pytest.fail(f"{path.relative_to(_SRC)} imports provider package(s): {sorted(leaked)}")


@pytest.mark.parametrize(
    "path",
    sorted(p for p in _SRC.rglob("*.py") if p.parent.name != "models"),
    ids=lambda p: str(p.relative_to(_SRC)),
)
def test_provider_response_fields_parsed_only_in_models(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    for token in _PROVIDER_RESPONSE_TOKENS:
        assert token not in source, f"{path.relative_to(_SRC)} references {token!r}"
