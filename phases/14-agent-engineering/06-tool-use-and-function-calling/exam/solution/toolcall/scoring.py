"""Grade a model's calls in the style of the Berkeley Function Calling Leaderboard (BFCL).

Live and Non-Live cases are graded by matching the calls (AST matching), Multi-Turn and Agentic
cases by the API state the calls leave behind (the state-based check BFCL V3 introduced), and
the five V4 categories are weighted 40/30/10/10/10.
"""
from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .cases import AST_CATEGORIES, CATEGORIES, STATE_CATEGORIES, WEIGHTS, Call, Case
from .drive import FakeDrive
from .registry import ToolCall


@dataclass(frozen=True)
class Verdict:
    case_id: str
    category: str
    correct: bool
    reason: str = ""  # why the case is wrong; "" when it is correct


@dataclass(frozen=True)
class Report:
    scores: dict[str, float | None]  # accuracy for every category; None when it has no verdicts
    counts: dict[str, int]  # verdicts per category
    total: float | None


def ast_match(calls: list[Call], accepted: list[list[Call]], tools: list[dict[str, Any]]) -> bool:
    """True when the calls are one of the accepted answers.

    The calls and an answer pair up one to one, in any order: parallel calls have no order,
    but each accepted call is matched once, so a repeated, extra or missing call is wrong.
    Two calls are the same when they name the same catalog tool and their arguments agree
    after every omitted parameter that has a schema "default" is filled in, on both sides;
    a parameter without a default must be given on both sides or on neither. A "number"
    parameter compares by value (21 and 21.0 agree). Every other value compares by value and
    JSON type, so "4", 4 and 4.0 are three different integers: the checker grades what the
    model wrote and does not coerce. A call to a tool outside the catalog, or with an
    argument its schema does not define, matches nothing. Matching never changes the calls
    or the answers.
    """
    schemas = {tool["name"]: tool["input_schema"] for tool in tools}
    mine = [_canonical(call, schemas) for call in calls]
    if None in mine:
        return False
    want = Counter(mine)
    for answer in accepted:
        theirs = [_canonical(call, schemas) for call in answer]
        if None not in theirs and Counter(theirs) == want:
            return True
    return False


def _canonical(call: Call, schemas: dict[str, dict[str, Any]]) -> tuple[str, str] | None:
    """A hashable form of the call in which equal calls are equal, or None if it matches nothing."""
    schema = schemas.get(call.name)
    if schema is None:
        return None
    props = schema.get("properties", {})
    if any(name not in props for name in call.args):
        return None
    args = {name: prop["default"] for name, prop in props.items() if "default" in prop}
    args.update(call.args)
    for name, value in args.items():
        number = isinstance(value, (int, float)) and not isinstance(value, bool)
        if number and props[name].get("type") == "number":
            args[name] = float(value)
    return call.name, json.dumps(args, sort_keys=True)


def state_match(calls: list[Call], case: Case) -> bool:
    """True when replaying the calls leaves the drive exactly in the case's expected state.

    The calls replay in order, from a copy of the case's initial state, through
    FakeDrive.registry(case.tools): only the tools the case offered can run, and arguments are
    validated and coerced the way the runtime would. A call that fails (an unknown tool,
    invalid arguments, a missing file) changes nothing, and the replay goes on, as the model
    saw the error and carried on. Grading never changes the case.
    """
    drive = FakeDrive(copy.deepcopy(case.initial_state))
    registry = drive.registry(case.tools)
    for number, call in enumerate(calls, 1):
        registry.dispatch(ToolCall(f"replay-{number}", call.name, call.args))
    return drive.state == case.expected_state


def grade(case: Case, calls: list[Call] | None) -> Verdict:
    """Grade one case. calls is everything the model called, in order; None means no attempt.

    Live and Non-Live are graded by ast_match against the accepted answers (reason "no accepted
    answer matches"). Multi-Turn and Agentic are graded by state_match; their calls need not
    match any answer (reason "final state differs"). A Hallucination case is correct only when
    the model called nothing at all (reason "a tool was called"). No attempt is wrong in every
    category, Hallucination included (reason "no attempt").
    """
    if calls is None:
        return Verdict(case.case_id, case.category, False, "no attempt")
    if case.category == "hallucination":
        correct, reason = not calls, "a tool was called"
    elif case.category in STATE_CATEGORIES:
        correct, reason = state_match(calls, case), "final state differs"
    elif case.category in AST_CATEGORIES:
        correct, reason = ast_match(calls, case.accepted, case.tools), "no accepted answer matches"
    else:
        raise ValueError(f"unknown category {case.category!r}")
    return Verdict(case.case_id, case.category, correct, "" if correct else reason)


def summarize(verdicts: list[Verdict]) -> Report:
    """Accuracy per category first, then the weighted total.

    scores has every category of CATEGORIES: the share of its verdicts that are correct, or
    None when it has no verdicts. The total weighs each category's accuracy by WEIGHTS
    (40/30/10/10/10) over the categories that have verdicts, with those weights rescaled to
    sum to 1; with no verdicts at all the total is None.
    """
    counts = {category: 0 for category in CATEGORIES}
    right = {category: 0 for category in CATEGORIES}
    for verdict in verdicts:
        if verdict.category not in counts:
            raise ValueError(f"unknown category {verdict.category!r}")
        counts[verdict.category] += 1
        right[verdict.category] += verdict.correct
    scores = {c: right[c] / counts[c] if counts[c] else None for c in CATEGORIES}
    present = [c for c in CATEGORIES if counts[c]]
    if not present:
        return Report(scores, counts, None)
    weight = sum(WEIGHTS[c] for c in present)
    total = sum(WEIGHTS[c] * scores[c] for c in present) / weight
    return Report(scores, counts, total)


def score_run(cases: list[Case], attempts: dict[str, list[Call]]) -> Report:
    """Grade a run. attempts maps case ids to the model's calls; a case missing from it had no
    attempt. An attempt for a case that is not in the run raises ValueError."""
    stray = sorted(set(attempts) - {case.case_id for case in cases})
    if stray:
        raise ValueError(f"attempts for cases that are not in the run: {stray}")
    return summarize([grade(case, attempts.get(case.case_id)) for case in cases])
