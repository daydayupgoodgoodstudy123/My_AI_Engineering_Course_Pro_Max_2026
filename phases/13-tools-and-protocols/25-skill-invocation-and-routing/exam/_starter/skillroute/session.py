"""Skills across a multi-turn session: their lifecycle stages, emitted as NDJSON."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Union

from .policy import Actor, InvocationRequest
from .router import Router


@dataclass(frozen=True)
class UserTurn:
    """A user message. It starts the next turn."""

    text: str


@dataclass(frozen=True)
class Approve:
    """The user allows these tools."""

    tools: tuple[str, ...]


@dataclass(frozen=True)
class ToolCall:
    """The model calls a tool while working under a skill."""

    skill: str
    tool: str


@dataclass(frozen=True)
class Compaction:
    """The host compacted the conversation."""


@dataclass(frozen=True)
class Check:
    """The independent success check of a skill's output."""

    skill: str
    passed: bool


@dataclass(frozen=True)
class Body:
    """A skill's instructions as loaded into the context."""

    skill: str
    revision: str
    text: str


Event = Union[UserTurn, Approve, ToolCall, Compaction, Check]


async def lifecycle(
    events: AsyncIterator[Event],
    router: Router,
    load_body: Callable[[str], Body],
) -> AsyncIterator[str]:
    """Follow every skill through its stages, one JSON object per line, as each stage happens.

    Every line is {"turn": n, "skill": name, "stage": stage} plus, by stage:
        eligible   "actor": "human" or "model"
        selected   "score": the router's score
        activated  "revision": the revision of the body load_body returned
        reloaded   "revision": likewise
        executing  "tool"
        denied     "reason", and "tool" when a tool call was refused
        completed  nothing more

    - Each UserTurn starts the next turn; the first is turn 1.
    - "/name ..." asks for that skill by name, as the human. Other text, when no skill is
      active, lets the model route implicitly; when a skill is active, the turn simply
      continues the active skills.
    - A request the router activates emits eligible, selected and activated. The body is
      loaded with load_body, and the skill stays active over the following turns. An explicit
      request the router refuses emits denied with the router's reason; an implicit request that
      activates nothing emits nothing. Asking for a skill that is already active emits nothing.
    - Approve allows its tools until the turn ends.
    - Compaction drops the body of every active skill; the skills stay active. Before a skill's
      next tool call its body is loaded again, which emits reloaded.
    - A ToolCall under an active skill emits executing when the tool is allowed in this turn,
      and otherwise denied with reason "tool not approved in this turn". Under a skill that is
      not active it emits denied with reason "skill not active".
    - A passing Check completes an active skill: completed, and the skill is no longer active.
      A failing Check emits nothing, and the skill stays active.
    """
    raise NotImplementedError
