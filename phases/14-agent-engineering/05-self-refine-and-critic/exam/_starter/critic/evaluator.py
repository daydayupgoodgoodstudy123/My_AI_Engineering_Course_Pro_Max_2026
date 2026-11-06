"""CRITIC with tools inside an evaluator-optimizer loop.

Every bullet of a draft is one claim. The evaluator routes each claim to the tool for its kind
(a calculator for arithmetic, a reference store standing in for search for everything else) and
turns the answers into a critique; the optimizer is the model's refine step.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .loop import Attempt, Model, bullet_lines


class ToolUnavailable(Exception):
    """A verification tool could not answer: an outage, a timeout, a rate limit."""


@dataclass(frozen=True)
class Check:
    """A tool's answer for one claim."""

    status: str  # "supported", "contradicted" or "unknown"
    evidence: str = ""  # what the tool found, e.g. "17 * 23 = 391"


# A tool takes a batch of claims and returns one Check per claim, in the same order.
Tool = Callable[[list[str]], list[Check]]


@dataclass(frozen=True)
class Finding:
    bullet: int  # 1-based position of the bullet in the draft
    claim: str  # the bullet's text without its "- " marker
    kind: str  # "math" or "fact"
    status: str  # "supported", "contradicted" or "unverified"
    evidence: str


@dataclass(frozen=True)
class Critique:
    findings: tuple[Finding, ...]  # one per bullet, in bullet order

    @property
    def passed(self) -> bool:
        """Every claim is supported by a tool. A draft with no claims has nothing grounded."""
        return bool(self.findings) and all(f.status == "supported" for f in self.findings)

    def text(self) -> str:
        """What the optimizer is told: one line per claim that is not supported, in bullet order."""
        lines = [f"bullet {f.bullet} {f.status}: {f.evidence}" for f in self.findings if f.status != "supported"]
        return "\n".join(lines) if lines else "all claims supported"


ARITHMETIC = re.compile(r"[\d\s.()+\-*/]+=\s*-?\d+(?:\.\d+)?")


def claim_kind(claim: str) -> str:
    """'math' for an arithmetic claim such as '17 * 23 = 391', otherwise 'fact'."""
    return "math" if ARITHMETIC.fullmatch(claim.strip()) else "fact"


def verify_claims(output: str, tools: dict[str, Tool]) -> Critique:
    """CRITIC's verify step: route every bullet to the tool for its kind and collect the answers.

    Each bullet ("- " line) is one claim, its text without the marker, and claim_kind picks its
    tool from tools. A tool is called once, with all of its claims in bullet order, and a tool with
    nothing to check is not called.
    A claim is "unverified" when its tool answers "unknown" (evidence: the tool's), when the tool
    raises ToolUnavailable (evidence: the exception's message), or when tools has no tool for its
    kind (evidence: "no <kind> tool"). The findings are in bullet order.
    """
    raise NotImplementedError


@dataclass(frozen=True)
class Outcome:
    status: str  # "passed" or "escalated"
    reason: str  # "" when passed, otherwise why a person has to look
    history: tuple[Attempt, ...]  # every round that was verified


def refine_until_verified(task: str, model: Model, tools: dict[str, Tool], max_rounds: int = 3) -> Outcome:
    """Evaluator-optimizer: verify_claims evaluates, model.refine optimizes, until a round passes.

    Every round verifies the current output and records an Attempt (critique: Critique.text(),
    grounded: True). A round whose critique passes ends the loop with status "passed". Otherwise,
    checked in this order, the loop escalates to a person with one of these reasons:

    - "unverified: bullets 2, 4" when no claim is contradicted but some are unverified, since
      refining cannot fix a claim no tool could check;
    - "budget: round 3 of 3" when max_rounds rounds have run;
    - "no progress: round 3 repeats round 1" when refine returns an output that an earlier round
      already had; that output is not verified again.

    Refine gets the critique text and the history so far.
    """
    raise NotImplementedError
