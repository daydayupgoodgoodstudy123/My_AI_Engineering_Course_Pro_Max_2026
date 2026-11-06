"""The subagent tree behind list_subkeys: rendering and expiry."""
from __future__ import annotations

from harness.store import SessionStore


def _parents(store: SessionStore) -> dict[str, str]:
    """Each subagent session's parent. ValueError if a session has two parents or the links loop."""
    parent_of: dict[str, str] = {}
    for sid in store.list_sessions():
        for sub in store.list_subkeys(sid):
            if sub in parent_of:
                raise ValueError(f"session {sub!r} is linked under {parent_of[sub]!r} and {sid!r}")
            parent_of[sub] = sid
    reached = sum(len(_preorder(store, sid)) for sid in store.list_sessions() if sid not in parent_of)
    if reached != len(store.list_sessions()):
        raise ValueError("subagent links loop")
    return parent_of


def _preorder(store: SessionStore, root: str) -> list[tuple[str, int]]:
    """(session, depth) pairs from root down, children in link order."""
    out: list[tuple[str, int]] = []
    stack = [(root, 0)]
    while stack:
        sid, depth = stack.pop()
        out.append((sid, depth))
        stack.extend((sub, depth + 1) for sub in reversed(store.list_subkeys(sid)))
    return out


def render_tree(store: SessionStore, root: str) -> str:
    """The subagent tree under root as indented text, one line per session.

    Each line is "  " * depth + f"{session_id}  turns={own} subtree={total}",
    where own counts the session's turns and total adds every session below
    it. Children come in the order they were linked, and every line ends with
    "\\n". Trees are as deep as the agents nest them.

    ValueError if root does not exist, if any session in the store is linked
    under two parents, or if the links loop.
    """
    if root not in store.list_sessions():
        raise ValueError(f"no session {root!r}")
    _parents(store)
    order = _preorder(store, root)
    total: dict[str, int] = {}
    for sid, _ in reversed(order):
        total[sid] = len(store.load(sid)) + sum(total[sub] for sub in store.list_subkeys(sid))
    return "".join(
        f"{'  ' * depth}{sid}  turns={len(store.load(sid))} subtree={total[sid]}\n"
        for sid, depth in order
    )


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
    parent_of = _parents(store)
    sessions = store.list_sessions()
    roots = [sid for sid in sessions if sid not in parent_of]
    live: dict[str, bool] = {}
    expired: list[str] = []
    for root in roots:
        order = _preorder(store, root)
        for sid, _ in reversed(order):
            turns = store.load(sid)
            own = bool(turns) and now - max(turn.ts for turn in turns) <= ttl_s
            live[sid] = own or any(live[sub] for sub in store.list_subkeys(sid))
            if not live[sid]:
                expired.append(sid)
    gone = set(expired)
    for sid in expired:
        if parent_of.get(sid) not in gone:
            store.delete(sid)
    return sorted(expired)
