"""Replay a multi-turn tool chain whose arguments point at the results of earlier calls."""
from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Callable

_HEAD = re.compile(r"\$([A-Za-z0-9_-]+)\.result")
_STEP = re.compile(r"\.([A-Za-z_][A-Za-z0-9_]*)|\[([0-9]+)\]")


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
    position: dict[str, int] = {}
    for index, step in enumerate(steps):
        if step.call_id in position:
            raise ChainError(f"call id {step.call_id!r} is used twice", step.call_id)
        position[step.call_id] = index
    for index, step in enumerate(steps):
        for text in _strings(step.args):
            parsed = _parse(text, step.call_id)
            if parsed is None:
                continue
            target = parsed[0]
            if target not in position:
                raise ChainError(f"{text}: no call {target!r} in the chain", step.call_id, text)
            if position[target] >= index:
                where = "itself" if target == step.call_id else "a later call"
                raise ChainError(f"{text}: {step.call_id} refers to {where}", step.call_id, text)

    results: dict[str, Any] = {}
    ran: list[Ran] = []
    for step in steps:
        args = _resolve(step.args, step.call_id, results)
        result = execute(step.name, args)
        results[step.call_id] = result
        ran.append(Ran(step.call_id, step.name, args, result))
    return ran


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _parse(text: str, call_id: str) -> tuple[str, list[tuple[str | int, int]]] | None:
    """(target call id, [(field or index, end offset in text)]) for a reference, else None."""
    head = _HEAD.match(text)
    if head is None:
        return None
    steps: list[tuple[str | int, int]] = []
    pos = head.end()
    while pos < len(text):
        step = _STEP.match(text, pos)
        if step is None:
            raise ChainError(f"{text!r} is not a valid reference", call_id, text)
        field, index = step.groups()
        steps.append((field if field is not None else int(index), step.end()))
        pos = step.end()
    return head.group(1), steps


def _resolve(value: Any, call_id: str, results: dict[str, Any]) -> Any:
    if isinstance(value, str):
        parsed = _parse(value, call_id)
        return value if parsed is None else _follow(value, parsed, call_id, results)
    if isinstance(value, dict):
        return {key: _resolve(item, call_id, results) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, call_id, results) for item in value]
    return value


def _follow(ref: str, parsed: tuple[str, list[tuple[str | int, int]]], call_id: str,
            results: dict[str, Any]) -> Any:
    target, steps = parsed
    value = results[target]
    for key, end in steps:
        if isinstance(key, str):
            if not isinstance(value, dict) or key not in value:
                raise ChainError(f"{ref}: nothing at {ref[:end]}", call_id, ref, ref[:end])
        elif not isinstance(value, list) or key >= len(value):
            raise ChainError(f"{ref}: nothing at {ref[:end]}", call_id, ref, ref[:end])
        value = value[key]
    return copy.deepcopy(value)
