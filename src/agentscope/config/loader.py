"""Load :class:`PublicConfig` from a typed configuration file (design 8.1).

Public settings are authored in a TOML file loaded at bootstrap. ``.env`` is not
consulted: environment overrides for public settings are intentionally not
supported. If operational overrides are later required they must be an explicit,
allowlisted layer.

Example::

    [models.regular]
    provider = "openrouter"
    model_name = "anthropic/claude-sonnet-4.6"
    credential_ref = "openrouter_api_key"

    [models.fast]
    provider = "meta"
    model_name = "muse-spark-1.3"
    credential_ref = "meta_model_api_key"
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from agentscope.config.public import PublicConfig

__all__ = ["load_public_config"]


def load_public_config(path: str | Path) -> PublicConfig:
    """Parse ``path`` as TOML and validate it into a :class:`PublicConfig`."""
    raw = Path(path).read_bytes()
    data = tomllib.loads(raw.decode("utf-8"))
    return PublicConfig.model_validate(data)
