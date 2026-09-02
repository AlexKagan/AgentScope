"""Repository security hygiene checks (design 13.5, 17)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _check_ignored(rel: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", rel],
        cwd=_ROOT,
        check=False,
    )
    return result.returncode == 0


@pytest.mark.parametrize("name", [".env", ".env.local", ".env.production"])
def test_env_files_are_ignored(name: str) -> None:
    assert _check_ignored(name), f"{name} is not git-ignored"


def test_env_example_is_not_ignored() -> None:
    assert (_ROOT / ".env.example").exists()
    assert not _check_ignored(".env.example")


def test_env_example_has_no_realistic_credentials() -> None:
    text = (_ROOT / ".env.example").read_text(encoding="utf-8")
    assert not re.search(r"sk-[A-Za-z0-9]{20,}", text)
    assert not re.search(r"\b[A-Fa-f0-9]{32,}\b", text)


def test_no_tracked_dotenv() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert ".env" not in tracked


def test_secret_scanning_is_configured_or_deferred() -> None:
    precommit = _ROOT / ".pre-commit-config.yaml"
    adr = _ROOT / "docs" / "adr" / "0010-secret-scanning-with-gitleaks.md"
    has_gitleaks = precommit.exists() and "gitleaks" in precommit.read_text(encoding="utf-8")
    documented = adr.exists()
    assert has_gitleaks or documented


@pytest.mark.parametrize("pkg", ["bootstrap", "architectures", "config", "runtime", "telemetry"])
def test_each_package_has_readme(pkg: str) -> None:
    assert (_ROOT / "src" / "agentscope" / pkg / "README.md").exists()
