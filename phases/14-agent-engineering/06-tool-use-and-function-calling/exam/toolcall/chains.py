"""Replay a multi-turn tool chain whose arguments point at the results of earlier calls."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Step:
    """One call of a recorded chain, before its references are resolved."""

    call_id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class Ran:
    """One call as it ran: its arguments with every reference resolved, and its result."""

    call_id: str
    name: str
    args: dict[str, Any]
    result: Any


class ChainError(ValueError):
    """A chain that cannot run as written.

    call_id is the step at fault (the step whose arguments hold the bad reference, or the
    repeated id), ref the reference text, and at the part of the reference that could not be
    followed: from "$" up to and including the step that failed. ref and at are None when they
    do not apply (at is None for a reference that is rejected before anything runs).
    """

    def __init__(self, message: str, call_id: str, ref: str | None = None, at: str | None = None):
        super().__init__(message)
        self.call_id = call_id
        self.ref = ref
        self.at = at


def run_chain(steps: list[Step], execute: Callable[[str, dict[str, Any]], Any]) -> list[Ran]:
    """Run the steps in order through execute(name, args), each exactly once.

    A reference is a string argument that starts with "$<call id>.result": that call's result,
    then any number of ".field" and "[index]" steps into it, as in
    "$call_1.result.items[0].path". A field name is letters, digits and underscores and does
    not start with a digit; an index is a non-negative decimal integer. The reference is
    replaced by the value it points at, with its type (a number stays a number, an object an
    object). References can sit anywhere in the arguments, inside nested objects and arrays.
    Any other string is passed as is, including one that mentions a reference inside other
    text, and so is everything that comes out of a result: results are data and are never
    resolved again.

    Before any step runs, ChainError is raised for two steps with the same call id, for a
    reference to the step itself, to a later step or to an unknown call, and for a string that
    starts like a reference but does not parse ("$call_1.result.items[-1]"). While the chain
    runs, a reference that cannot be followed (a missing field, an index out of range, a field
    of something that is not an object, an index into something that is not an array) raises
    ChainError for its step, which does not run; the steps before it have run. The steps
    themselves are never modified.
    """
    raise NotImplementedError
