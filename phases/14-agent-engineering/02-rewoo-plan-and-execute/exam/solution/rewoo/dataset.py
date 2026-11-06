"""Teacher plans for planner distillation, kept as JSON Lines.

The planner never sees observations, so (question, plan) pairs written by a large teacher model
can fine-tune a small planner. This file is where those pairs collect.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .plan import Plan, Step, references


@dataclass(frozen=True)
class Example:
    """One teacher trace: the question, the plan the teacher wrote, its final answer, and the judge's score."""

    question: str
    plan: Plan
    answer: str
    score: float  # from 0 to 1


class PlanDataset:
    """An append-only JSONL file of teacher examples.

    Each example is one line holding one JSON object:

        {"question": ..., "steps": [{"id": "E1", "tool": "search", "args": {...}}, ...],
         "answer": ..., "score": ...}

    Every field reads back exactly as it was appended: argument values keep their types and their
    order, and #E references stay as the teacher wrote them. A trainer may read the file while the
    teacher job is still appending to it, and a new PlanDataset on the same path carries on where
    the file ends.
    """

    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path)
        self._keys: set[str] | None = None

    def append(self, example: Example) -> bool:
        """Store an example and return True, or return False if it is already in the dataset.

        A duplicate is an example whose question and steps are exactly those of a stored example,
        argument types included: 1, 1.0 and True are three different values.

        An example that cannot be used for training raises ValueError and writes nothing: an empty
        question, a score that is not a number from 0 to 1, an empty plan, a repeated step id, or a
        reference to a step that is not in the plan.
        """
        _check(example)
        record = _record(example)
        key = _key(record)
        if self._keys is None:
            self._keys = {_key(stored) for stored in self._read()}
        if key in self._keys:
            return False
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        self._keys.add(key)
        return True

    def examples(self, min_score: float = 0.0) -> list[Example]:
        """The stored examples whose score is at least min_score, in the order they were appended."""
        return [ex for ex in map(_example, self._read()) if ex.score >= min_score]

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


def _check(example: Example) -> None:
    if not isinstance(example.question, str) or not example.question.strip():
        raise ValueError("an example needs a question")
    score = example.score
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
        raise ValueError(f"score must be a number from 0 to 1, got {score!r}")
    steps = example.plan.steps
    if not steps:
        raise ValueError("an example needs at least one step")
    ids = [step.id for step in steps]
    if len(set(ids)) != len(ids):
        raise ValueError(f"step ids repeat: {ids}")
    for step in steps:
        for ref in references(step.args):
            if ref not in ids:
                raise ValueError(f"step {step.id} refers to {ref}, which is not in the plan")


def _record(example: Example) -> dict:
    return {
        "question": example.question,
        "steps": [{"id": s.id, "tool": s.tool, "args": s.args} for s in example.plan.steps],
        "answer": example.answer,
        "score": example.score,
    }


def _key(record: dict) -> str:
    # json.dumps writes 1, 1.0 and true differently, where Python's == and hash() would not tell them apart.
    return json.dumps([record["question"], record["steps"]])


def _example(record: dict) -> Example:
    steps = [Step(s["id"], s["tool"], s["args"]) for s in record["steps"]]
    return Example(record["question"], Plan(steps), record["answer"], record["score"])
