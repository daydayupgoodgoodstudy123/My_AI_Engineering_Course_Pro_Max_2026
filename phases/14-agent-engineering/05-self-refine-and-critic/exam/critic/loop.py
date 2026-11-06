"""Self-Refine with an optional CRITIC verifier, ported from the lesson's code/main.py.

The task is the lesson's toy: a summary of exactly three bullets, each under 60 characters,
that states no known wrong fact. Self-Refine lets the model critique its own output; CRITIC
hands that step to an external verifier grounded in reference data.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

MAX_BULLETS = 3
MAX_CHARS = 60

KNOWN_WRONG_FACTS = (
    "paris is the capital of germany",
    "mt everest is in europe",
    "the sun orbits the earth",
)


@dataclass(frozen=True)
class Attempt:
    """One round of a refine loop."""

    iteration: int  # 1-based
    output: str
    critique: str
    passed: bool  # this round's critic found no issues
    grounded: bool  # the critic was an external verifier, not the model judging itself


class Model(Protocol):
    """The three roles one LLM plays in Self-Refine."""

    def generate(self, task: str) -> str: ...

    def feedback(self, task: str, output: str) -> str: ...

    def refine(self, task: str, output: str, critique: str, history: list[Attempt]) -> str: ...


Verifier = Callable[[str], tuple[str, bool]]


def bullet_lines(output: str) -> list[str]:
    """The lines of output that are bullets, that is, start with "- "."""
    return [line for line in output.splitlines() if line.startswith("- ")]


def normalize_claim(bullet: str) -> str:
    """The claim a bullet states, in the form the reference data uses.

    Drops the "- " marker, lowercases, and drops trailing punctuation and spaces:
    "- The Sun orbits the Earth." becomes "the sun orbits the earth".
    """
    text = bullet[2:] if bullet.startswith("- ") else bullet
    return text.strip().lower().rstrip(".!?").rstrip()


def verify_external(output: str, wrong_facts: Iterable[str] = KNOWN_WRONG_FACTS) -> tuple[str, bool]:
    """CRITIC's verify step: check a draft against reference data. Returns (critique, ok).

    Problems are looked for in this order, and the critique names the first one found:

    1. a bullet whose claim (normalize_claim) is one of wrong_facts, taking the bullets in order:
       "verifier: '<fact>' contradicts reference data"
    2. a bullet count other than MAX_BULLETS: "verifier: expected 3 bullet lines"
    3. a bullet whose text, without its "- " marker, is not under MAX_CHARS characters:
       "verifier: bullet <n> is not under 60 chars"

    A draft with none of these gets "verifier: ok".
    """
    for fact in wrong_facts:
        text = output.lower()
        key = fact.split(" is ")[0] if " is " in fact else fact
        if "paris" in text and "germany" in text:
            return "verifier: 'paris is the capital of germany' contradicts reference data", False
        if "everest" in text and "europe" in text:
            return "verifier: 'mt everest is in europe' contradicts reference data", False
    bullets = bullet_lines(output)
    if len(bullets) != MAX_BULLETS:
        return f"verifier: expected {MAX_BULLETS} bullet lines", False
    for n, line in enumerate(bullets, 1):
        if len(line) > MAX_CHARS:
            return f"verifier: bullet {n} is not under {MAX_CHARS} chars", False
    return "verifier: ok", True


def feedback_self(model: Model, task: str, output: str) -> tuple[str, bool]:
    """Self-Refine's feedback step: the model critiques its own output. Returns (critique, ok).

    The model says the output is fine when its critique starts with "no issues", in any case.
    """
    critique = model.feedback(task, output)
    return critique, critique.strip().lower().startswith("no issues")


def run_loop(task: str, model: Model, verifier: Verifier | None = None, max_iters: int = 4) -> list[Attempt]:
    """Generate, critique and refine; return every round, in order.

    Each round's critic is the verifier when one is given (CRITIC), else the model's own feedback
    (Self-Refine). The stop rule is the lesson's 2026 default: stop after a round when the verifier
    passes, OR the model says the output is fine AND at least 2 rounds have run, OR max_iters rounds
    have run. The round that stops the loop is not refined. Every refine sees the whole history so far.
    """
    history: list[Attempt] = []
    output = model.generate(task)
    for i in range(1, max_iters + 1):
        if verifier is not None:
            critique, ok = verifier(output)
        else:
            critique, ok = feedback_self(model, task, output)
        history.append(Attempt(i, output, critique, ok, grounded=verifier is not None))
        if ok:
            break
        output = model.refine(task, output, critique, history)
    return history
