"""Multi-round flows as a graph of phases.

Each MRTR round is one phase: the server asks the client for one input, validates the answer,
and the outcome of that validation picks the next phase. DONE ends the flow. The server keeps
nothing between rounds, so the state it seals into the next requestState carries the phase,
the round number and every validated value so far:

    {"phase": "narrow", "round": 2, "data": {"pick": [...]}}
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .protocol import McpError, sampling_text

DONE = "done"


@dataclass(frozen=True)
class Phase:
    ask: str  # the inputRequests key this phase asks the client to answer
    then: dict[str, str]  # outcome -> next phase, or DONE


def plan(start: str, phases: dict[str, Phase], max_rounds: int) -> int:
    """Check a flow when the server starts, and return the most rounds a run of it can take.

    A run starts at start and spends one round in every phase it visits; DONE is not a round.
    Raises ValueError if start or a next phase is not defined, if a phase has no outcomes, if a
    phase cannot be reached from start, if the phases form a cycle, or if the longest run takes
    more than max_rounds rounds. Two phases may lead to the same phase.
    """
    if start not in phases:
        raise ValueError(f"start phase {start!r} is not defined")
    for name, phase in phases.items():
        if not phase.then:
            raise ValueError(f"phase {name!r} has no outcomes")
        for target in phase.then.values():
            if target != DONE and target not in phases:
                raise ValueError(f"phase {name!r} leads to undefined phase {target!r}")

    rounds_from: dict[str, int] = {}
    on_path: set[str] = set()

    def longest(name: str) -> int:
        if name == DONE:
            return 0
        if name in on_path:
            raise ValueError(f"phase {name!r} is part of a cycle")
        if name not in rounds_from:
            on_path.add(name)
            rounds_from[name] = 1 + max(longest(target) for target in phases[name].then.values())
            on_path.discard(name)
        return rounds_from[name]

    rounds = longest(start)
    unreachable = sorted(set(phases) - set(rounds_from))
    if unreachable:
        raise ValueError(f"phases never reached from {start!r}: {unreachable}")
    if rounds > max_rounds:
        raise ValueError(f"a run can take {rounds} rounds, more than {max_rounds}")
    return rounds


def first_round(start: str) -> dict[str, Any]:
    """The state of a flow's first round."""
    return {"phase": start, "round": 1, "data": {}}


def advance(
    phases: dict[str, Phase],
    state: dict[str, Any],
    responses: Any,
    handle: Callable[[str, str, dict[str, Any]], tuple[Any, str]],
) -> dict[str, Any]:
    """Run one round of a flow on the state the server has just verified.

    responses must answer exactly the key the current phase asked for. Any other set of keys is
    McpError -32602: an answer meant for another phase, or a stale requestState sent with this
    round's answers. A state whose phase is not in the flow is -32602 too.
    handle(phase, text, data) checks the answer against data from earlier rounds and returns
    (value, outcome), or raises McpError. The value is recorded as data[phase], and the outcome
    picks the next phase from the phase's then; an outcome the phase does not list is a mistake in
    the flow itself and raises ValueError.
    Returns the next state with round + 1, or {"phase": DONE, ...} with the same round when the
    flow ends. state itself is left as it was.
    """
    name = state.get("phase")
    phase = phases.get(name)
    if phase is None:
        raise McpError(-32602, f"requestState phase {name!r} is not in this flow")
    if not isinstance(responses, dict) or set(responses) != {phase.ask}:
        raise McpError(-32602, f"this round answers {phase.ask!r} and nothing else")
    value, outcome = handle(name, sampling_text(responses, phase.ask), state["data"])
    target = phase.then.get(outcome)
    if target is None:
        raise ValueError(f"phase {name!r} has no outcome {outcome!r}")
    data = {**state["data"], name: value}
    if target == DONE:
        return {"phase": DONE, "round": state["round"], "data": data}
    return {"phase": target, "round": state["round"] + 1, "data": data}
