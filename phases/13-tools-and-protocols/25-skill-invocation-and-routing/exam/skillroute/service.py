"""The host's front door for explicit invocations: route, bind, then type."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Union

from .arguments import Param, bind, split_command, tool_arguments
from .policy import Actor, InvocationRequest
from .router import Router


@dataclass(frozen=True)
class Contract:
    """How this host binds one skill's arguments. It is adapter configuration, not portable frontmatter."""

    params: tuple[Param, ...] = ()
    schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})


@dataclass(frozen=True)
class Ready:
    skill: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class NeedsInput:
    skill: str
    missing: tuple[str, ...]


@dataclass(frozen=True)
class Refused:
    skill: str
    reason: str


Prepared = Union[Ready, NeedsInput, Refused]


class SkillHost:
    def __init__(self, router: Router, contracts: Mapping[str, Contract]) -> None:
        self.router = router
        self.contracts = dict(contracts)

    def prepare(self, text: str) -> Prepared:
        """Turn a human's /name invocation into the tool call the skill will make.

        The policy decides first: a refused skill never gets its arguments bound. Missing
        required arguments come back as NeedsInput, for the host to ask about.
        """
        name, argv = split_command(text)
        decision = self.router.route(InvocationRequest(Actor.HUMAN, text, explicit_name=name))
        if not decision.activated:
            return Refused(name, decision.reason)
        contract = self.contracts.get(name, Contract())
        binding = bind(contract.params, argv)
        if binding.missing:
            return NeedsInput(name, binding.missing)
        return Ready(name, tool_arguments(binding.values, contract.schema))
