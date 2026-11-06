"""Every session's handoff packet for one task, one JSON snapshot per session."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

SESSION_FILE = re.compile(r"session-([0-9]{4,})\.json")
ASSIGNED = ("session", "previous")


class HandoffHistory:
    """The handoff packets of one task, kept in root as session-<n>.json with n zero-padded to
    four digits (session-0007.json, session-0012.json).

    Other files can sit in root as well, such as session-0007.md, the Markdown render of a
    packet, an editor's backup like session-0007.json~, or notes a human left there. They are
    not sessions. root is created on the first save.
    """

    def __init__(self, root) -> None:
        self.root = Path(root)

    def sessions(self) -> list[int]:
        """The saved session numbers, lowest first. A missing root has none."""
        if not self.root.is_dir():
            return []
        found = (SESSION_FILE.fullmatch(path.name) for path in self.root.iterdir())
        return sorted(int(match.group(1)) for match in found if match)

    def save(self, packet: dict) -> int:
        """Save packet as the next session and return the session's number, counting from 1.

        The file holds packet's own keys and then the two the history assigns: "session", its
        number, and "previous", the number of the latest session before it (null for the first).
        A "session" or "previous" already in packet is replaced.

        Saving is idempotent, so a session-end hook that fires twice records one session: when
        packet, apart from those two keys, equals the latest saved packet apart from them, nothing
        is written and the latest number is returned. A packet equal to an older session is a new
        session; the task went back to an earlier state, and the history keeps that.

        The file is written whole or not at all: a temporary file in root, then os.replace.
        """
        done = self.sessions()
        own = {key: value for key, value in packet.items() if key not in ASSIGNED}
        if done:
            latest = self.load(done[-1])
            if own == {key: value for key, value in latest.items() if key not in ASSIGNED}:
                return done[-1]
        number = done[-1] + 1 if done else 1
        stored = {**own, "session": number, "previous": done[-1] if done else None}
        text = json.dumps(stored, indent=2, ensure_ascii=False) + "\n"
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".session-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, self.root / f"session-{number:04d}.json")
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        return number

    def load(self, session: int) -> dict:
        """The packet saved as session, exactly as stored. KeyError when there is no such session."""
        try:
            text = (self.root / f"session-{session:04d}.json").read_text(encoding="utf-8")
        except FileNotFoundError:
            raise KeyError(session) from None
        return json.loads(text)

    def latest(self) -> dict | None:
        """The packet with the highest session number, or None before the first save."""
        done = self.sessions()
        return self.load(done[-1]) if done else None
