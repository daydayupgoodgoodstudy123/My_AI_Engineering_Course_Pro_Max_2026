"""A session store mirrored to disk, one append-only JSONL file per session.

This is the --session-mirror idea: every turn reaches the session's mirror
file as it happens, so someone can tail the file while the agent runs.
"""
from __future__ import annotations

import json
from pathlib import Path

from harness.store import Turn

SUFFIX = ".jsonl"


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
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, list[Turn]] = {}
        self._subkeys: dict[str, list[str]] = {}
        for path in sorted(self.root.glob("*" + SUFFIX)):
            self._replay(bytes.fromhex(path.name[: -len(SUFFIX)]).decode("utf-8"), path)

    def _replay(self, session_id: str, path: Path) -> None:
        turns = self._sessions.setdefault(session_id, [])
        text = path.read_text(encoding="utf-8")
        for line in text.split("\n")[:-1]:
            record = json.loads(line)
            if "subagent" in record:
                self._subkeys.setdefault(session_id, []).append(record["subagent"])
            elif "removed" in record:
                subs = self._subkeys.get(session_id, [])
                self._subkeys[session_id] = [s for s in subs if s != record["removed"]]
            else:
                turns.append(Turn(record["role"], record["content"], record["ts"]))

    def mirror_path(self, session_id: str) -> Path:
        """The mirror file of session_id."""
        return self.root / (session_id.encode("utf-8").hex() + SUFFIX)

    def _write(self, session_id: str, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with open(self.mirror_path(session_id), "a", encoding="utf-8") as f:
            f.write(line)

    def _touch(self, session_id: str) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
            self.mirror_path(session_id).touch()

    def append(self, session_id: str, turn: Turn) -> None:
        self._touch(session_id)
        self._write(session_id, {"role": turn.role, "content": turn.content, "ts": turn.ts})
        self._sessions[session_id].append(turn)

    def load(self, session_id: str) -> list[Turn]:
        """The session's turns in order; [] for a session that does not exist."""
        return list(self._sessions.get(session_id, []))

    def list_sessions(self) -> list[str]:
        return sorted(self._sessions)

    def link_sub(self, parent: str, sub: str) -> None:
        self._touch(parent)
        self._touch(sub)
        self._write(parent, {"subagent": sub})
        self._subkeys.setdefault(parent, []).append(sub)

    def list_subkeys(self, session_id: str) -> list[str]:
        """The session's subagent sessions, in the order they were linked."""
        return list(self._subkeys.get(session_id, []))

    def delete(self, session_id: str) -> None:
        """Delete the session and every subagent session below it, at any depth.

        Their mirror files are removed. Deleted sessions also disappear from
        the subkeys of the sessions that remain, after a reopen too.
        Deleting a session that does not exist does nothing.
        """
        gone: set[str] = set()
        stack = [session_id]
        while stack:
            sid = stack.pop()
            if sid in gone or sid not in self._sessions:
                continue
            gone.add(sid)
            stack.extend(self._subkeys.pop(sid, []))
            del self._sessions[sid]
            self.mirror_path(sid).unlink()
        for parent, subs in self._subkeys.items():
            for sub in subs:
                if sub in gone:
                    self._write(parent, {"removed": sub})
            self._subkeys[parent] = [s for s in subs if s not in gone]
