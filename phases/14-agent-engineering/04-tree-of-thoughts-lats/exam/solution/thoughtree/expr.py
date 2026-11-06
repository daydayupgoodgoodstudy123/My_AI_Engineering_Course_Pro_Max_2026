"""Turn a solution's steps back into the expression they compute."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Union

from .game import Step, combine


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
    pool: list[tuple[Fraction, Expr]] = [(Fraction(n), Leaf(Fraction(n), i)) for i, n in enumerate(numbers)]
    for step in trace:
        left = _take(pool, step.a, step)
        right = _take(pool, step.b, step)
        if combine(step.a, step.op, step.b) != step.result:
            raise ValueError(f"wrong result in step {step}")
        pool.append((step.result, Op(step.op, left, right)))
    if len(pool) != 1:
        raise ValueError(f"the steps leave {len(pool)} expressions, not one")
    return pool[0][1]


def _take(pool: list[tuple[Fraction, Expr]], value: Fraction, step: Step) -> Expr:
    for k, (have, expr) in enumerate(pool):
        if have == value:
            del pool[k]
            return expr
    raise ValueError(f"step {step} uses {value}, which is not available")


def render(expr: Expr) -> str:
    """Write the expression in infix with as few parentheses as keep its meaning.

    An operand gets parentheses when its operator binds more loosely than its parent's (+ and -
    are looser than * and /). A right operand also gets them when the parent is - or / and both
    bind equally tightly: a - (b - c), a - (b + c), a / (b * c), a / (b / c). Otherwise there
    are none: (a - b) - c is a - b - c and a + (b - c) is a + b - c.
    Operators have a space on each side; numbers are written as integers.
    """
    if isinstance(expr, Leaf):
        return str(expr.value)
    mine = _PRECEDENCE[expr.op]
    left, right = render(expr.left), render(expr.right)
    if isinstance(expr.left, Op) and _PRECEDENCE[expr.left.op] < mine:
        left = f"({left})"
    if isinstance(expr.right, Op):
        theirs = _PRECEDENCE[expr.right.op]
        if theirs < mine or (theirs == mine and expr.op in "-/"):
            right = f"({right})"
    return f"{left} {expr.op} {right}"


def evaluate(expr: Expr) -> Fraction:
    """The exact value of the expression."""
    if isinstance(expr, Leaf):
        return expr.value
    result = combine(evaluate(expr.left), expr.op, evaluate(expr.right))
    if result is None:
        raise ZeroDivisionError("division by zero in the expression")
    return result
