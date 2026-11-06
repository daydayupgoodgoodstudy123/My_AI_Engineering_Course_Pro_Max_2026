"""Workbench audits, one CSV row each, appended to a scorecard file."""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime

from .report import WORKBENCH_SURFACES

COLUMNS = ["repo", "audited_at", *WORKBENCH_SURFACES, "notes"]
SCORES = (0, 1, 2)


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
        _validate(audit)
        new = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
        row = [audit.repo, audit.audited_at, *(audit.scores[s] for s in WORKBENCH_SURFACES), audit.notes]
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new:
                writer.writerow(COLUMNS)
            writer.writerow(row)

    def history(self, repo: str) -> list[Audit]:
        """Every audit of repo, oldest first by the instant in audited_at.

        Audits made at the same instant keep the order they were recorded in.
        """
        if not os.path.exists(self.path):
            return []
        with open(self.path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        audits = [_to_audit(row) for row in rows[1:] if row[0] == repo]
        return sorted(audits, key=lambda audit: datetime.fromisoformat(audit.audited_at))


def _validate(audit: Audit) -> None:
    if set(audit.scores) != set(WORKBENCH_SURFACES):
        raise ValueError(f"scores must cover exactly {WORKBENCH_SURFACES}, got {sorted(audit.scores)}")
    for surface, score in audit.scores.items():
        if score is not None and (type(score) is not int or score not in SCORES):
            raise ValueError(f"{surface}: a score is 0, 1, 2 or None, got {score!r}")
    if datetime.fromisoformat(audit.audited_at).utcoffset() is None:
        raise ValueError(f"audited_at needs a UTC offset, got {audit.audited_at!r}")


def _to_audit(row: list[str]) -> Audit:
    repo, audited_at, *scores, notes = row
    return Audit(
        repo,
        audited_at,
        {s: None if v == "" else int(v) for s, v in zip(WORKBENCH_SURFACES, scores)},
        notes,
    )
