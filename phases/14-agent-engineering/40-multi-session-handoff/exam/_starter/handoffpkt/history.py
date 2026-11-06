"""Every session's handoff packet for one task, one JSON snapshot per session."""
from __future__ import annotations

from pathlib import Path


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
        raise NotImplementedError

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
        raise NotImplementedError

    def load(self, session: int) -> dict:
        """The packet saved as session, exactly as stored. KeyError when there is no such session."""
        raise NotImplementedError

    def latest(self) -> dict | None:
        """The packet with the highest session number, or None before the first save."""
        raise NotImplementedError
