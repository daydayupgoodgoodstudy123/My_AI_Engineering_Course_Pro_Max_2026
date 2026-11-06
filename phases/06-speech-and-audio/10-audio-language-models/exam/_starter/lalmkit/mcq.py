"""Score MMAU-style multiple-choice answers from a model's free text."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    item_id: str
    category: str  # "speech", "sound", "music", "multi", ...
    question: str
    choices: list[str] | None  # None, or a single choice, for an open-ended item
    answer: str  # the text of the correct choice


def parse_choice(output: str | None, choices: list[str]) -> int | None:
    """The index of the choice a free-text answer picks, or None when it picks none or several.

    An answer names a choice by its letter (A for choices[0], B for choices[1], ...): a capital
    letter that stands alone and is followed by ")", "." or ":" or by the end of the answer, as
    in "(B)", "B." or "Answer: B". Or the whole answer is the text of one choice, ignoring case,
    surrounding spaces and a final period. Naming the same choice twice is still one choice.
    """
    raise NotImplementedError


def score(items: list[Item], outputs: dict[str, str | None]) -> dict:
    """Accuracy per category on the multiple-choice items, next to chance.

    Only items with at least two choices are multiple choice; the rest are skipped. An item is
    correct when its output picks the answer. A missing output, a failed call (None) or an answer
    that picks no single choice counts as wrong.

    Returns {"accuracy": {category: float}, "chance": {category: float},
             "count": {category: int}, "overall": float, "macro": float}.
    chance is what uniform random guessing scores: the mean of 1 / len(choices). overall is the
    accuracy over all scored items; macro is the plain mean of the per-category accuracies.
    """
    raise NotImplementedError
