"""Private helpers for deeply immutable JSON-like model-boundary values."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NoReturn, Self


class FrozenDict(dict[str, Any]):
    """A JSON-serializable ``dict`` subclass that rejects every mutation."""

    def _immutable(self) -> NoReturn:
        raise TypeError("mapping is immutable")

    def __setitem__(self, _key: str, _value: Any) -> None:
        self._immutable()

    def __delitem__(self, _key: str) -> None:
        self._immutable()

    def __ior__(self, _value: Any, /) -> Self:  # type: ignore[override,misc]
        self._immutable()

    def clear(self) -> None:
        self._immutable()

    def pop(self, _key: str, _default: Any = None) -> Any:
        self._immutable()

    def popitem(self) -> tuple[str, Any]:
        self._immutable()

    def setdefault(self, _key: str, _default: Any = None) -> Any:
        self._immutable()

    def update(self, *_args: Any, **_kwargs: Any) -> None:
        self._immutable()

    def copy(self) -> FrozenDict:
        return self


def deep_freeze(value: Any) -> Any:
    """Copy a JSON-like value into immutable mappings and sequences."""
    if isinstance(value, Mapping):
        return FrozenDict({str(key): deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(deep_freeze(item) for item in value)
    return value


def canonical_json_value(value: Any) -> Any:
    """Convert immutable JSON-like containers back to canonical JSON containers."""
    if isinstance(value, Mapping):
        return {str(key): canonical_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [canonical_json_value(item) for item in value]
    return value
