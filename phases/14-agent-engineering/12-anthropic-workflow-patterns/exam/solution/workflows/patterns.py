"""Four of Anthropic's five workflow patterns, as small async functions over an LLM callable.

An LLM here is any async callable that takes a prompt and returns the model's reply. The code owns
the path through the workflow; the model only fills in the steps. Orchestrator-workers, the fifth
pattern, lives in orchestrator.py.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

LLM = Callable[[str], Awaitable[str]]
Handler = Callable[[str], Awaitable[str]]


@dataclass(frozen=True)
class Step:
    """One step of a run: the node that ran, what it was given and what it returned."""

    name: str
    input: str
    output: str


class UnknownRoute(LookupError):
    """The classifier picked a label that has no handler, and no default handler is configured."""


async def prompt_chain(input_text: str, llm: LLM, steps: list[tuple[str, str]]) -> list[Step]:
    """Prompt chaining: the output of each step is the input of the next.

    Each step is (name, template). Every "{text}" in the template is replaced by the previous output
    (the input text for the first step). The rest of the template is sent exactly as written, so a
    template can show the model a literal JSON example. Returns one Step per call, in order.
    """
    current = input_text
    trace: list[Step] = []
    for name, template in steps:
        prompt = template.replace("{text}", current)
        output = await llm(prompt)
        trace.append(Step(name, prompt, output))
        current = output
    return trace


async def route(input_text: str, classifier: LLM, handlers: dict[str, Handler]) -> tuple[str, str]:
    """Routing: a classifier picks the handler for the input.

    The classifier's label is normalized first: surrounding whitespace removed, then lowercased, so
    "Refund\\n" picks the "refund" handler. Only a normalized label equal to a handler's key picks that
    handler. Any other label goes to handlers["default"] when there is one; otherwise route raises
    UnknownRoute naming the label. Returns (label, output) with the normalized label.
    """
    label = (await classifier(input_text)).strip().lower()
    handler = handlers.get(label) or handlers.get("default")
    if handler is None:
        raise UnknownRoute(f"no handler for label {label!r}")
    return label, await handler(input_text)


async def parallel_vote(prompt: str, llm: LLM, n: int = 5) -> tuple[str, Counter]:
    """Parallelization by voting: ask the same prompt n times and take the majority answer.

    All n calls are in flight at once. As soon as one answer has more than half of the n votes, it
    wins, and counts holds every vote that has come back by then. The calls still running are
    cancelled, and parallel_vote returns only after they have ended, so no call outlives the vote.
    When no answer gets more than half, every vote is waited for and counted: the most common answer
    wins, and a tie goes to the tied answer whose first vote was asked for first, whatever order the
    replies come back in. Returns (winner, counts).
    """
    calls = [asyncio.ensure_future(llm(prompt)) for _ in range(n)]
    try:
        counts: Counter = Counter()
        for reply in asyncio.as_completed(calls):
            answer = await reply
            counts[answer] += 1
            if counts[answer] * 2 > n:
                return answer, counts
    finally:
        # However the vote ends, stop the calls still running and wait until they have ended.
        for call in calls:
            call.cancel()
        await asyncio.gather(*calls, return_exceptions=True)
    # No majority, so every vote is in. Count them in the order they were asked for: most_common
    # keeps the first-inserted answer on a tie.
    votes = [call.result() for call in calls]
    counts = Counter(votes)
    winner, _ = counts.most_common(1)[0]
    return winner, counts


@dataclass(frozen=True)
class Round:
    """One evaluator-optimizer round: the candidate, the evaluator's verdict and its feedback."""

    candidate: str
    passed: bool
    feedback: str


@dataclass(frozen=True)
class Refined:
    """The result of evaluator_optimizer: the passing candidate (or None) and every round."""

    output: str | None
    rounds: list[Round]


Proposer = Callable[[str, "str | None"], Awaitable[str]]
Evaluator = Callable[[str, str], Awaitable[tuple[bool, str]]]


async def evaluator_optimizer(
    task: str, proposer: Proposer, evaluator: Evaluator, max_iter: int = 3
) -> Refined:
    """Evaluator-optimizer: one LLM proposes, another judges, and the judge's feedback goes back.

    proposer(task, feedback) returns a candidate; feedback is None in the first round and the
    evaluator's latest feedback after that. evaluator(task, candidate) returns (passed, feedback).
    The loop stops at the first passing candidate or after max_iter rounds, and max_iter must be at
    least 1 (ValueError otherwise). output is the passing candidate, or None when no round passed,
    so a draft the evaluator rejected is never returned as the answer.
    """
    if max_iter < 1:
        raise ValueError(f"max_iter must be at least 1, got {max_iter}")
    rounds: list[Round] = []
    feedback: str | None = None
    for _ in range(max_iter):
        candidate = await proposer(task, feedback)
        ok, feedback = await evaluator(task, candidate)
        rounds.append(Round(candidate, ok, feedback))
        if ok:
            return Refined(candidate, rounds)
    return Refined(None, rounds)
