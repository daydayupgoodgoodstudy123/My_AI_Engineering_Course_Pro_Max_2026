"""Two reviewers' evidence-backed opinions, reconciled into one report.

The lesson's answer to judge bias includes rotating judges across model families, and the
reviewer skill rejects any report that omits citations: every score must point at a file or a
trace entry. Here two reviewers score the same artifacts, each citing its evidence, and the
service turns their drafts into one report for the human.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .rubric import RUBRIC, DimensionScore, ReviewerInputs, ReviewReport


@dataclass(frozen=True)
class Opinion:
    """One reviewer's score for one dimension, with the evidence it cites."""

    dimension: str
    score: int
    note: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class Draft:
    """Everything one reviewer said about one task."""

    reviewer: str
    opinions: list[Opinion]


@dataclass(frozen=True)
class Reconciled:
    report: ReviewReport
    escalate: list[str]
    unsupported: list[tuple[str, str]]


def reconcile(inputs: ReviewerInputs, first: Draft, second: Draft, rubric: Sequence[str] = RUBRIC) -> Reconciled:
    """Turn two reviewers' drafts of the same task into one report.

    Evidence: a citation is "file:<path>" for a touched path, "feedback:<command_id>" for a
    feedback record, "finding:<code>" for a gate finding, or "state:<key>" for a state entry.
    Citations match exactly; paths are case-sensitive. An opinion is supported when it cites
    at least one thing and every citation is in the inputs. An unsupported score counts as at
    most 1, and every unsupported opinion is listed as (reviewer, dimension): the first
    reviewer's first, each in rubric order.

    Each dimension's score is the mean of the two counted scores, rounded down. A dimension
    escalates to a human when the two counted scores differ by more than 1; escalation changes
    no score and not the verdict. Verdict: hard_fail when any dimension is 0 or the total is
    below 5, soft_fail when it is below 7, pass otherwise. The report's dimensions follow the
    rubric, and each note reads "<first reviewer>: <note> | <second reviewer>: <note>".

    Each draft must give exactly one opinion per rubric dimension, else ValueError.
    """
    known = _evidence(inputs)
    drafts = [(draft.reviewer, _by_dimension(draft, rubric)) for draft in (first, second)]
    counted: list[dict[str, int]] = []
    unsupported: list[tuple[str, str]] = []
    for reviewer, opinions in drafts:
        scores: dict[str, int] = {}
        for name in rubric:
            opinion = opinions[name]
            if opinion.evidence and all(c in known for c in opinion.evidence):
                scores[name] = opinion.score
            else:
                scores[name] = min(opinion.score, 1)
                unsupported.append((reviewer, name))
        counted.append(scores)
    a, b = counted
    dims: list[DimensionScore] = []
    escalate: list[str] = []
    for name in rubric:
        note = f"{first.reviewer}: {drafts[0][1][name].note} | {second.reviewer}: {drafts[1][1][name].note}"
        dims.append(DimensionScore(name, (a[name] + b[name]) // 2, note))
        if abs(a[name] - b[name]) > 1:
            escalate.append(name)
    total = sum(d.score for d in dims)
    if any(d.score == 0 for d in dims) or total < 5:
        verdict = "hard_fail"
    elif total < 7:
        verdict = "soft_fail"
    else:
        verdict = "pass"
    return Reconciled(ReviewReport(inputs.task_id, total, verdict, dims), escalate, unsupported)


def _evidence(inputs: ReviewerInputs) -> set[str]:
    known = {f"file:{path}" for path in inputs.diff_summary.get("touched", [])}
    known |= {f"feedback:{rec['command_id']}" for rec in inputs.feedback if "command_id" in rec}
    known |= {f"finding:{f['code']}" for f in inputs.verdict.get("findings", [])}
    known |= {f"state:{key}" for key in inputs.state}
    return known


def _by_dimension(draft: Draft, rubric: Sequence[str]) -> dict[str, Opinion]:
    opinions: dict[str, Opinion] = {}
    for opinion in draft.opinions:
        if opinion.dimension in opinions:
            raise ValueError(f"{draft.reviewer} scores {opinion.dimension} twice")
        opinions[opinion.dimension] = opinion
    missing = [name for name in rubric if name not in opinions]
    unknown = [name for name in opinions if name not in rubric]
    if missing or unknown:
        raise ValueError(f"{draft.reviewer} must score exactly the rubric: missing {missing}, unknown {unknown}")
    return opinions
