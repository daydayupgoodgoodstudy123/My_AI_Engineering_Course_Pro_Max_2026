"""Turns and the in-memory session store.

The surface follows the Agent SDK's session store: append, load, list_sessions,
delete (with cascade to subagent sessions) and list_subkeys. link_sub records
that one session is a subagent of another.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Turn:
    role: str
    content: str
    ts: float = 0.0


class SessionStore:
    """Sessions kept in memory.

    A session exists once it has a turn or takes part in a link.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[Turn]] = {}
        self._subkeys: dict[str, list[str]] = {}

    def append(self, session_id: str, turn: Turn) -> None:
        self._sessions.setdefault(session_id, []).append(turn)

    def load(self, session_id: str) -> list[Turn]:
        """The session's turns in order; [] for a session that does not exist."""
        return list(self._sessions.get(session_id, []))

    def list_sessions(self) -> list[str]:
        return sorted(self._sessions)

    def link_sub(self, parent: str, sub: str) -> None:
        self._sessions.setdefault(parent, [])
        self._sessions.setdefault(sub, [])
        self._subkeys.setdefault(parent, []).append(sub)

    def list_subkeys(self, session_id: str) -> list[str]:
        """The session's subagent sessions, in the order they were linked."""
        return list(self._subkeys.get(session_id, []))

    def delete(self, session_id: str) -> None:
        """Delete the session and every subagent session below it, at any depth.

        Deleted sessions also disappear from the subkeys of the sessions that
        remain. Deleting a session that does not exist does nothing.
        """
        gone: set[str] = set()
        stack = [session_id]
        while stack:
            sid = stack.pop()
            if sid in gone:
                continue
            gone.add(sid)
            self._sessions.pop(sid, None)
            stack.extend(self._subkeys.pop(sid, []))
        for parent, subs in self._subkeys.items():
            self._subkeys[parent] = [s for s in subs if s not in gone]
