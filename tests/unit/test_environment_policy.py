"""Unit tests for allowlist-based sandbox env construction (design 8.5, 13.1)."""

from __future__ import annotations

import ast
import inspect

import pytest

from agentscope.runtime import environment
from agentscope.runtime.environment import (
    SANDBOX_BASE_ENV,
    build_sandbox_environment,
    reject_host_env_lookup,
)
from agentscope.runtime.errors import DisallowedEnvVarError, HostEnvLookupError


def test_empty_request_returns_base_only() -> None:
    env = build_sandbox_environment()
    assert env == SANDBOX_BASE_ENV
    assert env is not SANDBOX_BASE_ENV  # fresh copy


def test_allowlisted_var_is_forwarded_literally() -> None:
    env = build_sandbox_environment({"LANG": "en_US.UTF-8"})
    assert env["LANG"] == "en_US.UTF-8"


def test_non_allowlisted_var_is_omitted_by_default() -> None:
    env = build_sandbox_environment({"OPENAI_API_KEY": "sk-x", "FOO": "bar"})
    assert "OPENAI_API_KEY" not in env
    assert "FOO" not in env


def test_non_allowlisted_var_is_rejected_in_strict_mode() -> None:
    with pytest.raises(DisallowedEnvVarError):
        build_sandbox_environment({"FOO": "bar"}, strict=True)


def test_values_are_not_interpolated() -> None:
    env = build_sandbox_environment({"LANG": "$HOME/${PATH}"})
    assert env["LANG"] == "$HOME/${PATH}"


def test_host_environment_is_never_consulted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTSCOPE_OPENAI_API_KEY", "sk-should-not-appear")
    monkeypatch.setenv("SECRET_TOKEN", "tok-should-not-appear")
    env = build_sandbox_environment()
    joined = "".join(f"{k}={v}" for k, v in env.items())
    assert "should-not-appear" not in joined


def test_module_never_reads_os_environ() -> None:
    tree = ast.parse(inspect.getsource(environment))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(a.name != "os" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "os"
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"environ", "getenv"}
        if isinstance(node, ast.Name):
            assert node.id not in {"environ", "getenv"}


def test_reject_host_env_lookup_always_raises() -> None:
    with pytest.raises(HostEnvLookupError):
        reject_host_env_lookup("PATH")
