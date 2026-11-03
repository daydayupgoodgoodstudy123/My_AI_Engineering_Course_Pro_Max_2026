"""Skills across a multi-turn session: their lifecycle stages, emitted as NDJSON."""
from __future__ import annotations

import json
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
    turn = 0
    allowed: set[str] = set()
    bodies: dict[str, Body | None] = {}  # active skills; None once compaction dropped the body

    def line(skill: str, stage: str, **extra: object) -> str:
        return json.dumps({"turn": turn, "skill": skill, "stage": stage, **extra}) + "\n"

    async for event in events:
        if isinstance(event, UserTurn):
            turn += 1
            allowed = set()
            text = event.text.strip()
            if text.startswith("/"):
                name = text[1:].split(maxsplit=1)[0] if text[1:].strip() else ""
                request = InvocationRequest(Actor.HUMAN, text, explicit_name=name)
            elif bodies:
                continue
            else:
                request = InvocationRequest(Actor.MODEL, text)
            decision = router.route(request)
            if decision.activated:
                name = decision.skill_name
                if name in bodies:
                    continue
                body = load_body(name)
                bodies[name] = body
                yield line(name, "eligible", actor=request.actor.value)
                yield line(name, "selected", score=decision.score)
                yield line(name, "activated", revision=body.revision)
            elif request.actor is Actor.HUMAN:
                yield line(request.explicit_name, "denied", reason=decision.reason)
        elif isinstance(event, Approve):
            allowed.update(event.tools)
        elif isinstance(event, Compaction):
            for name in bodies:
                bodies[name] = None
        elif isinstance(event, ToolCall):
            if event.skill not in bodies:
                yield line(event.skill, "denied", reason="skill not active", tool=event.tool)
                continue
            if bodies[event.skill] is None:
                body = load_body(event.skill)
                bodies[event.skill] = body
                yield line(event.skill, "reloaded", revision=body.revision)
            if event.tool in allowed:
                yield line(event.skill, "executing", tool=event.tool)
            else:
                yield line(event.skill, "denied", reason="tool not approved in this turn", tool=event.tool)
        elif isinstance(event, Check):
            if event.passed and event.skill in bodies:
                del bodies[event.skill]
                yield line(event.skill, "completed")
        else:
            raise TypeError(f"unknown event {event!r}")
