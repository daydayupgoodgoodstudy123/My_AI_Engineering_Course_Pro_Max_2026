"""Turn a solution's steps back into the expression they compute."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Union

from .game import Step


@dataclass(frozen=True)
class Leaf:
    value: Fraction
    index: int  # position of the number in the deal


@dataclass(frozen=True)
class Op:
    op: str
    left: Expr
    right: Expr


Expr = Union[Leaf, Op]

_PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2}


def build(numbers: list[int], trace: list[Step]) -> Expr:
    """Rebuild the expression tree that a solution's steps compute.

    Keep a pool of operands: a Leaf for every number of the deal, in deal order, then each
    step's result, added at the end as it is made. A step takes its a from the pool (the
    earliest operand in the pool with that value), then its b from what is left, and puts
    Op(op, a, b) at the end of the pool. A deal of one number with no steps is that Leaf.
    Raises ValueError when a step uses a number the pool does not have, when its result is not
    a op b, or when the steps do not leave exactly one expression.
    """
    raise NotImplementedError


def render(expr: Expr) -> str:
    """Write the expression in infix with as few parentheses as keep its meaning.

    An operand gets parentheses when its operator binds more loosely than its parent's (+ and -
    are looser than * and /). A right operand also gets them when the parent is - or / and both
    bind equally tightly: a - (b - c), a - (b + c), a / (b * c), a / (b / c). Otherwise there
    are none: (a - b) - c is a - b - c and a + (b - c) is a + b - c.
    Operators have a space on each side; numbers are written as integers.
    """
    raise NotImplementedError


def evaluate(expr: Expr) -> Fraction:
    """The exact value of the expression."""
    raise NotImplementedError
