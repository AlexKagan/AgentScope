"""Contract tests: implementations satisfy the architecture contract (design 13.3)."""

from __future__ import annotations

from agentscope.architectures.base import AgentArchitecture
from agentscope.architectures.identity import ArchitectureIdentity
from agentscope.architectures.registry import ArchitectureRegistry
from tests._fakes import DummyArchitecture


def test_dummy_satisfies_protocol() -> None:
    arch = DummyArchitecture()
    assert isinstance(arch, AgentArchitecture)
    assert isinstance(arch.identity, ArchitectureIdentity)
    assert isinstance(arch.describe(), str)


def test_factory_output_satisfies_protocol() -> None:
    reg = ArchitectureRegistry()
    reg.register_factory("dummy_agent", lambda: DummyArchitecture())
    resolved = reg.resolve("dummy_agent")
    assert isinstance(resolved, AgentArchitecture)
    assert resolved.identity.architecture_key == "dummy_agent"
