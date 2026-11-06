"""The Game of 24 as a search problem: states, steps, children, and the judge ToT relies on.

A state is the multiset of numbers still to combine, kept as a tuple sorted largest first.
Arithmetic is exact: every number is a Fraction, so 8 / (3 - 8 / 3) is exactly 24.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from typing import NamedTuple

TARGET = Fraction(24)
OPS = ("+", "-", "*", "/")

State = tuple[Fraction, ...]


class Step(NamedTuple):
    """One thought: a op b. The operands keep their order, so 1 - 5 is Step(1, "-", 5, -4)."""

    a: Fraction
    op: str
    b: Fraction
    result: Fraction

    def __str__(self) -> str:
        return f"{_operand(self.a)} {self.op} {_operand(self.b)} = {self.result}"


def _operand(x: Fraction) -> str:
    """Integers as they are; fractions and negative numbers in parentheses, so 8 / (1/3) reads right."""
    return str(x) if x.denominator == 1 and x >= 0 else f"({x})"


def start(numbers: list[int]) -> State:
    """The root state of a deal: every number as a Fraction, largest first."""
    return tuple(sorted(numbers, reverse=True))


def combine(a: Fraction, op: str, b: Fraction) -> Fraction | None:
    """a op b, exactly. A division by zero has no result."""
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a / b if b != 0 else None
    raise ValueError(f"unknown operation {op!r}")


def children(state: State) -> list[tuple[Step, State]]:
    """Every state one step below this one, with the step that leads there.

    A step takes the numbers at two positions i < j, a = state[i] and b = state[j], and puts one
    result back; the new state is sorted largest first. + and * give one child per pair, while
    - and / give one for each order. For every pair the children come in the order
    a + b, a - b, b - a, a * b, a / b, b / a, and a division by zero gives no child.
    Children that reach the same state are all listed: deduplication is the search's job.
    """
    out: list[tuple[Step, State]] = []
    for i, j in combinations(range(len(state)), 2):
        a, b = state[i], state[j]
        rest = state[:i] + state[i + 1 : j] + state[j + 1 :]
        for op in OPS:
            result = combine(a, op, b)
            if result is not None:
                out.append((Step(a, op, b, result), tuple(sorted(rest + (result,), reverse=True))))
    return out


def solved(state: State) -> bool:
    """One number is left, and it is 24."""
    return state == (TARGET,)


_SOLVABLE: dict[State, bool] = {}


def solvable(state: State) -> bool:
    """Can these numbers still make 24? Exhaustive, with a table of the states already decided."""
    known = _SOLVABLE.get(state)
    if known is None:
        if len(state) == 1:
            known = solved(state)
        else:
            known = any(solvable(child) for _, child in children(state))
        _SOLVABLE[state] = known
    return known


def value(state: State) -> float:
    """The ToT judge: how promising a state is, on the sure / likely / impossible scale.

    The judge works states of up to three numbers out completely: sure (1.0) if they can still
    make 24, impossible (0.0) if they cannot. With four or more numbers it can only say likely,
    scored 0.5 / (1 + d), where d is how far the number closest to 24 is from 24.
    A sure state is promising. It is not a solution until 24 is the only number left.
    """
    if len(state) <= 3:
        return 1.0 if solvable(state) else 0.0
    d = min(abs(x - TARGET) for x in state)
    return 0.5 / (1 + float(d))


def reward(state: State) -> float:
    """What the environment pays for a finished state (one number r): 1 / (1 + |r - 24|).

    Only 24 itself earns the full 1.0. The reward is computed exactly and rounded to a float once.
    """
    (r,) = state
    return float(1 / (1 + abs(r - TARGET)))
