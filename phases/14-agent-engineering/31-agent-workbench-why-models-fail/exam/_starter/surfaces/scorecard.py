"""Workbench audits, one CSV row each, appended to a scorecard file."""
from __future__ import annotations

from dataclasses import dataclass

from .report import WORKBENCH_SURFACES

COLUMNS = ["repo", "audited_at", *WORKBENCH_SURFACES, "notes"]


@dataclass(frozen=True)
class Audit:
    """One workbench audit of a repo (the lesson's Exercise 1 and its workbench-audit skill).

    scores holds every surface in WORKBENCH_SURFACES: 0 missing, 1 partial, 2 healthy, or
    None when the auditor refused to score it (a repo with no test command at all gets its
    verification score refused). audited_at is ISO 8601 with a UTC offset, as the auditor
    wrote it.
    """

    repo: str
    audited_at: str
    scores: dict[str, int | None]
    notes: str = ""


class Scorecard:
    """An append-only CSV of audits.

    The first row is COLUMNS, then one row per audit; a refused score is an empty field.
    Rows already in the file are never rewritten.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def record(self, audit: Audit) -> None:
        """Append one audit.

        An audit scores every surface exactly once (unknown surfaces are not allowed), each
        score is 0, 1, 2 or None, and audited_at carries a UTC offset. An audit that breaks
        any of these raises ValueError and leaves the file as it was.
        """
        raise NotImplementedError

    def history(self, repo: str) -> list[Audit]:
        """Every audit of repo, oldest first by the instant in audited_at.

        Audits made at the same instant keep the order they were recorded in.
        """
        raise NotImplementedError
