"""Pinned receipts: the lines a frame cites, stored by their sha256."""
from __future__ import annotations

from dataclasses import dataclass

from .frame import RepositoryFact
from .repo import Repo


@dataclass(frozen=True)
class Pin:
    """A line receipt as it was pinned: the claim, the cited place, the line's sha256."""

    claim: str
    path: str
    line: int
    digest: str


@dataclass(frozen=True)
class Verdict:
    """What a pinned receipt says about a newer snapshot (see ReceiptStore.recheck)."""

    claim: str
    status: str
    receipt: str | None


class ReceiptStore:
    """A content-addressed store in one directory.

    Every object is a file objects/<first 2 hex digits>/<other 62 hex digits> whose bytes
    hash (sha256) to that name, and storing the same bytes again changes nothing. A pinned
    line is stored as its UTF-8 bytes, exactly as the file has it, without the newline. The
    pins of one frame are stored the same way, as one JSON list.
    """

    def __init__(self, root: str) -> None:
        self.root = root

    def put(self, data: bytes) -> str:
        """Store bytes and return their sha256 hex digest."""
        raise NotImplementedError

    def get(self, digest: str) -> bytes:
        """The bytes stored under a digest. An unknown digest raises KeyError."""
        raise NotImplementedError

    def pin(self, facts: list[RepositoryFact], repo: Repo) -> str:
        """Pin the line receipts of facts against repo; return the digest of the pin list.

        Every line receipt becomes a Pin, in fact order, and its cited line is stored.
        Command receipts are observations with no line to pin and are left out. A receipt
        that does not resolve in repo raises ValueError.
        """
        raise NotImplementedError

    def pins(self, digest: str) -> list[Pin]:
        """The pins stored under a pin-list digest. An unknown digest raises KeyError."""
        raise NotImplementedError

    def recheck(self, digest: str, repo: Repo) -> list[Verdict]:
        """Check the pins under a pin-list digest against another snapshot, in pin order.

        "fresh"  the cited line still holds the pinned bytes; receipt is the same path:line
        "moved"  it does not, but exactly one line of the same file holds them; receipt
                 points there
        "stale"  neither: the bytes are gone, sit on several lines (which one the fact
                 meant would be a guess), or the file is gone; receipt is None

        Whitespace counts: a line that only lost its trailing spaces has changed.
        """
        raise NotImplementedError
