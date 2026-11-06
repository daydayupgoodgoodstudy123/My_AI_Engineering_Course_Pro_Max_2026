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
    raise NotImplementedError
