"""Sandbox environment construction by positive allowlisting (design 8.5).

The sandbox environment is built from an empty baseline plus a small set of
sandbox-local literals and explicitly approved safe variables. It is *never*
produced by copying the host process environment and removing known secret
names. This module never imports or reads the host process environment - a unit
test enforces that by parsing this source file.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import NoReturn

from agentscope.runtime.errors import DisallowedEnvVarError, HostEnvLookupError

__all__ = [
    "DEFAULT_ENV_ALLOWLIST",
    "SANDBOX_BASE_ENV",
    "build_sandbox_environment",
    "reject_host_env_lookup",
]

# Runtime essentials only. Every addition needs an explicit rationale and test.
DEFAULT_ENV_ALLOWLIST: frozenset[str] = frozenset({"LANG", "LC_ALL", "LC_CTYPE", "TZ"})

# Sandbox-local literal values - not read from, and unrelated to, the host.
SANDBOX_BASE_ENV: dict[str, str] = {
    "HOME": "/workspace",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "TMPDIR": "/tmp",  # noqa: S108 - sandbox-local path, not a host temp dir
}


def build_sandbox_environment(
    requested: Mapping[str, str] | None = None,
    *,
    allowlist: frozenset[str] = DEFAULT_ENV_ALLOWLIST,
    strict: bool = False,
) -> dict[str, str]:
    """Return a fresh sandbox environment: base literals + allowlisted requests.

    Values are used literally; no ``$VAR`` / ``${VAR}`` interpolation is ever
    performed. Non-allowlisted keys are omitted, or - when ``strict`` - rejected
    with :class:`DisallowedEnvVarError`.
    """
    env = dict(SANDBOX_BASE_ENV)
    for key, value in (requested or {}).items():
        if key not in allowlist:
            if strict:
                raise DisallowedEnvVarError(f"env var not on the allowlist: {key!r}")
            continue
        env[key] = str(value)  # literal; never expanded against any environment
    return env


def reject_host_env_lookup(name: str) -> NoReturn:
    """Always raise: there is no model-facing 'read a host env var' capability."""
    raise HostEnvLookupError(f"host environment lookup is not a supported capability: {name!r}")
