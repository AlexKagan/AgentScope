"""Unit tests for workspace path confinement (design 8.6, 13.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentscope.runtime.errors import PathEscapeError
from agentscope.runtime.workspace import (
    WorkspaceRelativePath,
    WorkspaceRoot,
    resolve_within,
)


@pytest.fixture
def root(tmp_path: Path) -> WorkspaceRoot:
    ws = tmp_path / "ws"
    (ws / "sub").mkdir(parents=True)
    return WorkspaceRoot(path=ws)


def test_relative_path_inside_workspace_resolves(root: WorkspaceRoot) -> None:
    resolved = resolve_within(root, "sub/file.txt")
    assert resolved == root.path / "sub" / "file.txt"


@pytest.mark.parametrize("bad", ["/etc/passwd", "/tmp/x"])
def test_absolute_paths_rejected(root: WorkspaceRoot, bad: str) -> None:
    with pytest.raises(PathEscapeError):
        resolve_within(root, bad)


@pytest.mark.parametrize("bad", ["../secret", "../../etc/passwd", "sub/../../b"])
def test_parent_traversal_rejected(root: WorkspaceRoot, bad: str) -> None:
    with pytest.raises(PathEscapeError):
        resolve_within(root, bad)


def test_symlink_escape_rejected(root: WorkspaceRoot, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("top secret")
    (root.path / "evil").symlink_to(outside / "secret.txt")
    with pytest.raises(PathEscapeError):
        resolve_within(root, "evil")


def test_symlink_that_stays_inside_is_allowed(root: WorkspaceRoot) -> None:
    (root.path / "sub" / "real.txt").write_text("hi")
    (root.path / "link.txt").symlink_to(root.path / "sub" / "real.txt")
    resolved = resolve_within(root, "link.txt")
    assert root.path in resolved.parents


def test_workspace_root_must_be_absolute_and_exist(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError):
        WorkspaceRoot(path=Path("relative/dir"))
    with pytest.raises(PathEscapeError):
        WorkspaceRoot(path=tmp_path / "does-not-exist")


def test_workspace_relative_path_parse_accepts_safe_values() -> None:
    assert WorkspaceRelativePath.parse("sub/dir/file.txt") == "sub/dir/file.txt"
    assert isinstance(WorkspaceRelativePath.parse("a.txt"), str)


@pytest.mark.parametrize("bad", ["/abs", "../up", "a/../../b"])
def test_workspace_relative_path_parse_rejects_escapes(bad: str) -> None:
    with pytest.raises(PathEscapeError):
        WorkspaceRelativePath.parse(bad)
