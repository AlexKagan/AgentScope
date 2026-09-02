"""Static guard: only bootstrap consumes SecretConfig (design 8.3, 13.2).

The check targets real *consumption* - importing the secret module or calling
``get_secret_value`` - not prose mentions in docstrings.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

import agentscope

_SRC = Path(agentscope.__file__).parent

# Modules allowed to import / consume the secret module.
_ALLOWED = {
    _SRC / "config" / "secret.py",
    _SRC / "bootstrap" / "composition.py",
    _SRC / "bootstrap" / "__init__.py",
    _SRC / "telemetry" / "phoenix.py",  # reads otlp_headers to build the exporter
}


def _imports_secret_module(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("config.secret"):
            return True
        if isinstance(node, ast.Import) and any(
            alias.name.endswith("config.secret") for alias in node.names
        ):
            return True
    return False


@pytest.mark.parametrize(
    "path",
    sorted(p for p in _SRC.rglob("*.py") if p not in _ALLOWED),
    ids=lambda p: str(p.relative_to(_SRC)),
)
def test_module_does_not_consume_secretconfig(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    rel = path.relative_to(_SRC)
    assert "get_secret_value" not in source, f"{rel} calls get_secret_value"
    assert not _imports_secret_module(ast.parse(source)), f"{rel} imports config.secret"


def test_secretconfig_not_reexported_from_config_package() -> None:
    config_pkg = importlib.import_module("agentscope.config")
    assert not hasattr(config_pkg, "SecretConfig")
    # It remains importable from its own module for the trusted consumer.
    secret_mod = importlib.import_module("agentscope.config.secret")
    assert hasattr(secret_mod, "SecretConfig")
