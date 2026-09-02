"""Workspace path confinement (design 8.6).

One shared validator resolves every model-facing path relative to the task
workspace root and rejects absolute paths, parent traversal, and symlink
escapes. Model-facing APIs never accept arbitrary host paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from agentscope.runtime.errors import PathEscapeError

__all__ = ["WorkspaceRelativePath", "WorkspaceRoot", "resolve_within"]


@dataclass(frozen=True, slots=True)
class WorkspaceRoot:
    """A canonicalized, existing directory that bounds all model-facing I/O."""

    path: Path

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise PathEscapeError(f"workspace root must be absolute: {self.path}")
        if not self.path.is_dir():
            raise PathEscapeError(f"workspace root must be an existing directory: {self.path}")
        # Store the fully resolved form so later containment checks are canonical.
        object.__setattr__(self, "path", self.path.resolve(strict=True))


class WorkspaceRelativePath(str):
    """A validated workspace-relative path string (no filesystem access)."""

    __slots__ = ()

    @classmethod
    def parse(cls, value: str) -> WorkspaceRelativePath:
        pure = PurePosixPath(value)
        if pure.is_absolute():
            raise PathEscapeError(f"path must be workspace-relative, got absolute: {value!r}")
        if any(part == ".." for part in pure.parts):
            raise PathEscapeError(f"path must not contain '..': {value!r}")
        return cls(value)


def resolve_within(root: WorkspaceRoot, candidate: str | PurePosixPath) -> Path:
    """Resolve ``candidate`` under ``root`` or raise :class:`PathEscapeError`.

    ``resolve`` collapses symlinks, so a link that points outside the workspace
    fails the containment check just like a literal ``..`` would.
    """
    pure = PurePosixPath(str(candidate))
    if pure.is_absolute():
        raise PathEscapeError(f"path must be workspace-relative, got absolute: {candidate!r}")
    if any(part == ".." for part in pure.parts):
        raise PathEscapeError(f"path must not contain '..': {candidate!r}")
    full = (root.path / pure).resolve()
    if full != root.path and root.path not in full.parents:
        raise PathEscapeError(f"path escapes the workspace: {candidate!r}")
    return full
