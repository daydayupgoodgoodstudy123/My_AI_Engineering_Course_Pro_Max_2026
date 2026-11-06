"""Rebuild a task's history from its handoff packets, across forks."""
from __future__ import annotations

from dataclasses import dataclass


class BrokenChain(ValueError):
    """A packet's previous session is not among the packets."""


@dataclass(frozen=True)
class BranchHead:
    """The active handoff of one branch: the packet the next session on that branch starts from."""

    branch: str
    session: int
    next_action: str
    open_risks: list[dict]
    lineage: list[int]


def branch_heads(packets: list[dict]) -> list[BranchHead]:
    """One BranchHead per branch, ordered by session number.

    Each packet has "session", "previous" (null for the first), "branch", "next_action",
    "open_risks" (risks raised or still open in that session, each with a stable "id") and
    "closed_risks" (ids resolved in that session). The packets may come in any order, and
    branch_heads leaves them as they came.

    A branch's head is its packet with the highest session number; older packets of that
    branch are superseded. lineage is the chain of previous pointers from the first session to
    the head, and it may cross branches: a branch forked from another one inherits everything
    before the fork. open_risks are the risks still open at the head, walking the lineage in
    order: a risk opens when a session lists it, a later listing with the same id replaces it in
    place (the wording may change, the id does not), and it closes when a session's
    closed_risks names it (applied after that session's open_risks). Risks are listed in the
    order they opened. Only the head's own lineage counts: what happens on another branch never
    opens or closes anything here.

    A previous session that is missing raises BrokenChain naming it. Two packets with one
    session number, or a previous that is not an earlier session, raise ValueError.
    """
    raise NotImplementedError
