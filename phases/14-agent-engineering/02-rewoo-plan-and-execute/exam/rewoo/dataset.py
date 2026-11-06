"""Teacher plans for planner distillation, kept as JSON Lines.

The planner never sees observations, so (question, plan) pairs written by a large teacher model
can fine-tune a small planner. This file is where those pairs collect.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .plan import Plan


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

    def append(self, example: Example) -> bool:
        """Store an example and return True, or return False if it is already in the dataset.

        A duplicate is an example whose question and steps are exactly those of a stored example,
        argument types included: 1, 1.0 and True are three different values.

        An example that cannot be used for training raises ValueError and writes nothing: an empty
        question, a score that is not a number from 0 to 1, an empty plan, a repeated step id, or a
        reference to a step that is not in the plan.
        """
        raise NotImplementedError

    def examples(self, min_score: float = 0.0) -> list[Example]:
        """The stored examples whose score is at least min_score, in the order they were appended."""
        raise NotImplementedError
