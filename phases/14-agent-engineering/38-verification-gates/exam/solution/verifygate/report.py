"""One report, one path: outputs/verification/<task_id>.json, which CI and humans both read."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .model import Verdict

_TASK_ID = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")


def write_report(root: str | Path, verdict: Verdict) -> Path:
    """Write the task's one verification report and return its path.

    The report lives at <root>/outputs/verification/<task_id>.json whatever ran the gate, so CI, the
    reviewer and a human all read the same file. It holds
    json.dumps(verdict.to_dict(), indent=2, sort_keys=True) and a newline, so the same verdict always
    gives the same bytes, and writing again replaces the file. A task id that is not a plain file name
    (letters, digits, ".", "_" and "-", not starting with ".") raises ValueError and nothing is written.
    """
    if not _TASK_ID.fullmatch(verdict.task_id):
        raise ValueError(f"task id {verdict.task_id!r} is not a plain file name")
    path = Path(root) / "outputs" / "verification" / f"{verdict.task_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(verdict.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path
