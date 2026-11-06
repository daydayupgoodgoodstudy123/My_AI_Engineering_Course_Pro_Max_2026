"""StateManager: load, validate and atomically persist one state file."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .schema import validate


def dump_state(state: Any) -> str:
    """The text of a state file: JSON indented by 2 spaces, ending in a newline."""
    return json.dumps(state, indent=2) + "\n"


def atomic_write(path: Path, content: str) -> None:
    """Replace the file at path with content; a crash leaves either the old file or the new one.

    Writes a temporary file in the same directory, flushes and fsyncs it, then renames it over
    the target with os.replace. A failed write removes the temporary file and raises.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


class StateManager:
    """One state file under one schema. A bad write is a refused write."""

    def __init__(self, state_path: Path, schema: dict[str, Any]) -> None:
        self.state_path = Path(state_path)
        self.schema = schema

    def load(self) -> Any:
        """Read the file and validate it. A file that breaks the schema raises SchemaError."""
        raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        validate(raw, self.schema)
        return raw

    def commit(self, state: Any) -> None:
        """Validate state, then write it atomically. A refused write leaves the file as it was."""
        validate(state, self.schema)
        atomic_write(self.state_path, dump_state(state))

    def update(self, **changes: Any) -> Any:
        """Apply one changes request as one atomic state transition and return it.

        Load and validate the current object, merge every given top-level field,
        then validate and commit the complete result once. Any rejected field
        leaves all prior bytes intact. A successful nonempty request performs
        one atomic replacement; an empty request only loads and returns state.
        """
        state = self.load()
        if changes:
            state.update(changes)
            self.commit(state)
        return state
