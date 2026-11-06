"""One report, one path: outputs/verification/<task_id>.json, which CI and humans both read."""
from __future__ import annotations

import json
from pathlib import Path

from .model import Verdict


def write_report(root: str | Path, verdict: Verdict) -> Path:
    """Write the task's one verification report and return its path.

    The report lives at <root>/outputs/verification/<task_id>.json whatever ran the gate, so CI, the
    reviewer and a human all read the same file. It holds
    json.dumps(verdict.to_dict(), indent=2, sort_keys=True) and a newline, so the same verdict always
    gives the same bytes, and writing again replaces the file. A task id that is not a plain file name
    (letters, digits, ".", "_" and "-", not starting with ".") raises ValueError and nothing is written.
    """
    raise NotImplementedError
