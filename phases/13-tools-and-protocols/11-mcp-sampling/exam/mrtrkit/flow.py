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
    raise NotImplementedError


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
    raise NotImplementedError
