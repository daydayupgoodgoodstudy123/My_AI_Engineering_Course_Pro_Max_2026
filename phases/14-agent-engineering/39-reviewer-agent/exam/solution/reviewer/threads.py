"""Review comment threads.

Every finding the reviewer raises starts a thread. The builder answers, the reviewer asks back,
and replies nest. Only the reviewer can resolve a thread: a builder saying "fixed" is a claim
for the reviewer to check, not a resolution.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .rubric import RUBRIC


@dataclass(frozen=True)
class Comment:
    id: str
    parent: str | None  # None: this comment is a finding, and it starts a thread
    author: str  # "reviewer" or "builder"
    at: int  # when it was posted, in seconds
    text: str
    dimension: str | None = None  # the rubric dimension a finding is about (findings only)
    resolve: bool = False  # the author marks the thread resolved with this comment


@dataclass(frozen=True)
class ThreadState:
    finding: str  # id of the finding that starts the thread
    dimension: str
    status: str  # "open" or "resolved"
    comments: int  # comments in the thread, the finding included
    last_at: int  # time of the thread's latest comment


@dataclass(frozen=True)
class ThreadSummary:
    threads: list[ThreadState]
    open_by_dimension: dict[str, int]
    self_resolved: list[str]


def summarize_threads(comments: Iterable[Comment], rubric: Sequence[str] = RUBRIC) -> ThreadSummary:
    """Work out which review threads are still open.

    A reply can answer any comment, at any depth, and belongs to the thread of the finding it
    leads back to. The comments come in no particular order: a reply may come before the
    comment it answers.

    A thread is resolved when the reviewer has resolved it and everything else in it is older:
    a comment posted at or after the reviewer's latest resolve, at any depth and by anyone,
    reopens it. A resolve by the builder resolves nothing. self_resolved lists the open threads
    in which the builder marked the thread resolved at or after the reviewer's latest resolve
    (or with no reviewer resolve at all).

    threads are ordered by the finding's time; open_by_dimension counts the open threads of
    every rubric dimension, in rubric order, zeros included; self_resolved follows the thread
    order. A finding whose dimension is not in the rubric, or a reply to a comment that is not
    in the review, raises ValueError naming that finding or reply.
    """
    comments = list(comments)
    by_id: dict[str, Comment] = {}
    for comment in comments:
        if comment.id in by_id:
            raise ValueError(f"comment id {comment.id!r} is used twice")
        by_id[comment.id] = comment
    members: dict[str, list[Comment]] = {}
    for comment in comments:
        top = comment
        seen = {top.id}
        while top.parent is not None:
            parent = by_id.get(top.parent)
            if parent is None:
                raise ValueError(f"comment {top.id!r} answers {top.parent!r}, which is not in the review")
            if parent.id in seen:
                raise ValueError(f"comment {comment.id!r} is part of a reply loop")
            seen.add(parent.id)
            top = parent
        members.setdefault(top.id, []).append(comment)

    position = {comment.id: i for i, comment in enumerate(comments)}
    rows: list[tuple[int, int, ThreadState, bool]] = []
    for finding_id, thread in members.items():
        finding = by_id[finding_id]
        if finding.dimension not in rubric:
            raise ValueError(f"finding {finding_id!r} is about {finding.dimension!r}, which is not a rubric dimension")
        resolves = [c.at for c in thread if c.resolve and c.author == "reviewer"]
        last_resolve = max(resolves) if resolves else None
        later = [c for c in thread if not (c.resolve and c.author == "reviewer")]
        resolved = last_resolve is not None and all(c.at < last_resolve for c in later)
        marked = any(
            c.resolve and c.author == "builder" and (last_resolve is None or c.at >= last_resolve)
            for c in thread
        )
        state = ThreadState(
            finding_id,
            finding.dimension,
            "resolved" if resolved else "open",
            len(thread),
            max(c.at for c in thread),
        )
        rows.append((finding.at, position[finding_id], state, marked and not resolved))
    rows.sort(key=lambda row: (row[0], row[1]))

    open_by_dimension = {name: 0 for name in rubric}
    for _, _, state, _ in rows:
        if state.status == "open":
            open_by_dimension[state.dimension] += 1
    return ThreadSummary(
        [state for _, _, state, _ in rows],
        open_by_dimension,
        [state.finding for _, _, state, self_marked in rows if self_marked],
    )
