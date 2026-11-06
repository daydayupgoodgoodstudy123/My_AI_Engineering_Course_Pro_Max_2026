"""A session store mirrored to disk, one append-only JSONL file per session.

This is the --session-mirror idea: every turn reaches the session's mirror
file as it happens, so someone can tail the file while the agent runs.
"""
from __future__ import annotations

from pathlib import Path

from harness.store import Turn


class MirrorStore:
    """Same surface and behaviour as SessionStore, kept in files under root
    (created if it is missing).

    Each session has one mirror file directly inside root. Any string is a
    valid session id: ids that contain "/" or "..", or differ only in case,
    still get a file of their own.

    Every line of a mirror file is one JSON object followed by "\\n":
      {"role": ..., "content": ..., "ts": ...}  a turn of this session
      {"subagent": "<id>"}                       a subagent linked under it
      {"removed": "<id>"}                        that subagent was deleted
    The mirror is for people to read while debugging, so non-ASCII text is
    written as it is, not as \\u escapes. Lines are only ever appended. A line
    is on disk before the call that wrote it returns.

    A new MirrorStore on the same root sees everything earlier stores wrote.
    """

    def __init__(self, root: Path) -> None:
        raise NotImplementedError

    def mirror_path(self, session_id: str) -> Path:
        """The mirror file of session_id."""
        raise NotImplementedError

    def append(self, session_id: str, turn: Turn) -> None:
        raise NotImplementedError

    def load(self, session_id: str) -> list[Turn]:
        """The session's turns in order; [] for a session that does not exist."""
        raise NotImplementedError

    def list_sessions(self) -> list[str]:
        raise NotImplementedError

    def link_sub(self, parent: str, sub: str) -> None:
        raise NotImplementedError

    def list_subkeys(self, session_id: str) -> list[str]:
        """The session's subagent sessions, in the order they were linked."""
        raise NotImplementedError

    def delete(self, session_id: str) -> None:
        """Delete the session and every subagent session below it, at any depth.

        Their mirror files are removed. Deleted sessions also disappear from
        the subkeys of the sessions that remain, after a reopen too.
        Deleting a session that does not exist does nothing.
        """
        raise NotImplementedError
