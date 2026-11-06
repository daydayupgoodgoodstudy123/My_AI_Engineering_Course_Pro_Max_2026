"""Two reviewers' evidence-backed opinions, reconciled into one report.

The lesson's answer to judge bias includes rotating judges across model families, and the
reviewer skill rejects any report that omits citations: every score must point at a file or a
trace entry. Here two reviewers score the same artifacts, each citing its evidence, and the
service turns their drafts into one report for the human.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .rubric import RUBRIC, ReviewerInputs, ReviewReport


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
    raise NotImplementedError
