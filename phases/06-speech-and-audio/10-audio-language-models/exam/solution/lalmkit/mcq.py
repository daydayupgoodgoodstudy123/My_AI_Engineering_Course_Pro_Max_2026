"""Score MMAU-style multiple-choice answers from a model's free text."""
from __future__ import annotations

import re
from dataclasses import dataclass

# A capital letter that stands alone and is followed by ")", ".", ":" or the end of the answer.
LETTER = re.compile(r"\b([A-Z])(?=[).:]|\s*$)")


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
    if output is None:
        return None
    picked = set()
    for match in LETTER.finditer(output):
        index = ord(match.group(1)) - ord("A")
        if index < len(choices):
            picked.add(index)
    text = output.strip().removesuffix(".").strip().lower()
    picked.update(i for i, choice in enumerate(choices) if choice.strip().lower() == text)
    return picked.pop() if len(picked) == 1 else None


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
    correct: dict[str, int] = {}
    count: dict[str, int] = {}
    guess: dict[str, float] = {}
    for item in items:
        if len(item.choices or []) < 2:
            continue
        picked = parse_choice(outputs.get(item.item_id), item.choices)
        c = item.category
        correct[c] = correct.get(c, 0) + (picked is not None and item.choices[picked] == item.answer)
        count[c] = count.get(c, 0) + 1
        guess[c] = guess.get(c, 0.0) + 1 / len(item.choices)
    if not count:
        raise ValueError("no multiple-choice items to score")
    accuracy = {c: correct[c] / count[c] for c in count}
    return {
        "accuracy": accuracy,
        "chance": {c: guess[c] / count[c] for c in count},
        "count": count,
        "overall": sum(correct.values()) / sum(count.values()),
        "macro": sum(accuracy.values()) / len(accuracy),
    }
