"""Grade a model's calls in the style of the Berkeley Function Calling Leaderboard (BFCL).

Live and Non-Live cases are graded by matching the calls (AST matching), Multi-Turn and Agentic
cases by the API state the calls leave behind (the state-based check BFCL V3 introduced), and
the five V4 categories are weighted 40/30/10/10/10.
"""
from __future__ import annotations

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
    raise NotImplementedError


def state_match(calls: list[Call], case: Case) -> bool:
    """True when replaying the calls leaves the drive exactly in the case's expected state.

    The calls replay in order, from a copy of the case's initial state, through
    FakeDrive.registry(case.tools): only the tools the case offered can run, and arguments are
    validated and coerced the way the runtime would. A call that fails (an unknown tool,
    invalid arguments, a missing file) changes nothing, and the replay goes on, as the model
    saw the error and carried on. Grading never changes the case.
    """
    raise NotImplementedError


def grade(case: Case, calls: list[Call] | None) -> Verdict:
    """Grade one case. calls is everything the model called, in order; None means no attempt.

    Live and Non-Live are graded by ast_match against the accepted answers (reason "no accepted
    answer matches"). Multi-Turn and Agentic are graded by state_match; their calls need not
    match any answer (reason "final state differs"). A Hallucination case is correct only when
    the model called nothing at all (reason "a tool was called"). No attempt is wrong in every
    category, Hallucination included (reason "no attempt").
    """
    raise NotImplementedError


def summarize(verdicts: list[Verdict]) -> Report:
    """Accuracy per category first, then the weighted total.

    scores has every category of CATEGORIES: the share of its verdicts that are correct, or
    None when it has no verdicts. The total weighs each category's accuracy by WEIGHTS
    (40/30/10/10/10) over the categories that have verdicts, with those weights rescaled to
    sum to 1; with no verdicts at all the total is None.
    """
    raise NotImplementedError


def score_run(cases: list[Case], attempts: dict[str, list[Call]]) -> Report:
    """Grade a run. attempts maps case ids to the model's calls; a case missing from it had no
    attempt. An attempt for a case that is not in the run raises ValueError."""
    raise NotImplementedError
