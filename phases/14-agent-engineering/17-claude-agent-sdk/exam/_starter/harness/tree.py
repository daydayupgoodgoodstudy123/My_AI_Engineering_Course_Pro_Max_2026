"""The subagent tree behind list_subkeys: rendering and expiry."""
from __future__ import annotations

from harness.store import SessionStore


def render_tree(store: SessionStore, root: str) -> str:
    """The subagent tree under root as indented text, one line per session.

    Each line is "  " * depth + f"{session_id}  turns={own} subtree={total}",
    where own counts the session's turns and total adds every session below
    it. Children come in the order they were linked, and every line ends with
    "\\n". Trees are as deep as the agents nest them.

    ValueError if root does not exist, if any session in the store is linked
    under two parents, or if the links loop.
    """
    raise NotImplementedError


def prune_expired(store: SessionStore, now: float, ttl_s: float) -> list[str]:
    """Delete the sessions that expired, and return their ids, sorted.

    A session is idle when its newest turn is more than ttl_s seconds before
    now; a session without turns is idle. It expires when it and every
    session below it, at any depth, are idle: a session with a live subagent
    is kept, however old it is. Deleted sessions disappear from
    list_sessions and from their parent's subkeys.

    ValueError if a session is linked under two parents or the links loop;
    then nothing is deleted.
    """
    raise NotImplementedError
