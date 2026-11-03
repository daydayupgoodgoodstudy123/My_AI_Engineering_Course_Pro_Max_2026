"""Labeled trigger cases for one skill's routing boundary."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# The case types of a trigger eval. Paraphrased positives are positives.
CATEGORIES = ("positive", "clear_negative", "near_miss", "competing", "adversarial")
NEGATIVE_CATEGORIES = CATEGORIES[1:]

_SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def is_skill_name(value: object) -> bool:
    """A valid skill name: lowercase kebab-case, at most 64 characters."""
    return isinstance(value, str) and len(value) <= 64 and _SKILL_NAME.fullmatch(value) is not None


@dataclass(frozen=True)
class TriggerCase:
    """One labeled prompt.

    expected_skill is the skill that should handle the prompt, or None when no skill should.
    For the skill under test, positive cases expect it and no other category does: a near miss
    or a competing case usually belongs to a neighbouring skill.
    """

    case_id: str
    prompt: str
    category: str
    expected_skill: str | None


def check_cases(cases: Sequence[TriggerCase], skill: str) -> None:
    """Raise ValueError unless cases are a well-formed trigger set for skill."""
    if not is_skill_name(skill):
        raise ValueError(f"invalid skill name {skill!r}")
    seen: set[str] = set()
    for case in cases:
        case_id = case.case_id
        if not isinstance(case_id, str) or not case_id.strip() or case_id != case_id.strip() or case_id in seen:
            raise ValueError("trigger case ids must be unique and non-empty, without surrounding whitespace")
        seen.add(case_id)
        if not isinstance(case.prompt, str) or not case.prompt.strip() or case.prompt != case.prompt.strip():
            raise ValueError(f"case {case_id!r}: a prompt must be non-empty, without surrounding whitespace")
        if case.category not in CATEGORIES:
            raise ValueError(f"case {case_id!r}: unknown category {case.category!r}")
        if case.expected_skill is not None and not is_skill_name(case.expected_skill):
            raise ValueError(f"case {case_id!r}: invalid expected skill {case.expected_skill!r}")
        if (case.category == "positive") != (case.expected_skill == skill):
            raise ValueError(f"case {case_id!r}: exactly the positive cases expect {skill}")


def check_predictions(cases: Sequence[TriggerCase], predictions: Mapping[str, Sequence[str | None]]) -> None:
    """Raise ValueError unless every case, and only those, has at least one run.

    Each run is the name of the skill the router invoked, or None where it abstained.
    """
    ids = [case.case_id for case in cases]
    if set(predictions) != set(ids):
        raise ValueError("predictions must cover exactly the declared cases")
    for case_id in ids:
        runs = predictions[case_id]
        if isinstance(runs, (str, bytes)) or len(runs) == 0:
            raise ValueError(f"case {case_id!r} needs at least one run")
        for value in runs:
            if value is not None and not is_skill_name(value):
                raise ValueError(f"case {case_id!r}: {value!r} is neither a skill name nor None (abstained)")
