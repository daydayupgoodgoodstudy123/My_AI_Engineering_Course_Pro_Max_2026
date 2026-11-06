"""Pinned receipts: the lines a frame cites, stored by their sha256."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass

from .frame import LineReceipt, RepositoryFact, parse_receipt, receipt_problem
from .repo import Repo

_DIGEST = re.compile(r"[0-9a-f]{64}")


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
        digest = hashlib.sha256(data).hexdigest()
        path = self._path(digest)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f"{path}.{os.getpid()}.tmp"
            with open(tmp, "wb") as out:
                out.write(data)
            os.replace(tmp, path)
        return digest

    def get(self, digest: str) -> bytes:
        """The bytes stored under a digest. An unknown digest raises KeyError."""
        if not _DIGEST.fullmatch(digest):
            raise KeyError(digest)
        try:
            with open(self._path(digest), "rb") as stored:
                return stored.read()
        except FileNotFoundError:
            raise KeyError(digest) from None

    def pin(self, facts: list[RepositoryFact], repo: Repo) -> str:
        """Pin the line receipts of facts against repo; return the digest of the pin list.

        Every line receipt becomes a Pin, in fact order, and its cited line is stored.
        Command receipts are observations with no line to pin and are left out. A receipt
        that does not resolve in repo raises ValueError.
        """
        receipts: list[tuple[RepositoryFact, LineReceipt]] = []
        for fact in facts:
            problem = receipt_problem(fact.evidence, repo)
            if problem is not None:
                raise ValueError(f"cannot pin {fact.claim!r}: {problem}")
            receipt = parse_receipt(fact.evidence)
            if isinstance(receipt, LineReceipt):
                receipts.append((fact, receipt))
        pins = [
            Pin(fact.claim, r.path, r.line, self.put(repo.line(r.path, r.line).encode("utf-8")))
            for fact, r in receipts
        ]
        listing = [{"claim": p.claim, "path": p.path, "line": p.line, "digest": p.digest} for p in pins]
        return self.put(json.dumps(listing, ensure_ascii=False, sort_keys=True).encode("utf-8"))

    def pins(self, digest: str) -> list[Pin]:
        """The pins stored under a pin-list digest. An unknown digest raises KeyError."""
        listing = json.loads(self.get(digest).decode("utf-8"))
        return [Pin(item["claim"], item["path"], item["line"], item["digest"]) for item in listing]

    def recheck(self, digest: str, repo: Repo) -> list[Verdict]:
        """Check the pins under a pin-list digest against another snapshot, in pin order.

        "fresh"  the cited line still holds the pinned bytes; receipt is the same path:line
        "moved"  it does not, but exactly one line of the same file holds them; receipt
                 points there
        "stale"  neither: the bytes are gone, sit on several lines (which one the fact
                 meant would be a guess), or the file is gone; receipt is None

        Whitespace counts: a line that only lost its trailing spaces has changed.
        """
        return [self._verdict(pin, repo) for pin in self.pins(digest)]

    def _verdict(self, pin: Pin, repo: Repo) -> Verdict:
        if pin.path not in repo:
            return Verdict(pin.claim, "stale", None)
        pinned = self.get(pin.digest).decode("utf-8")
        lines = repo.lines(pin.path)
        if pin.line <= len(lines) and lines[pin.line - 1] == pinned:
            return Verdict(pin.claim, "fresh", f"{pin.path}:{pin.line}")
        found = [number for number, text in enumerate(lines, 1) if text == pinned]
        if len(found) == 1:
            return Verdict(pin.claim, "moved", f"{pin.path}:{found[0]}")
        return Verdict(pin.claim, "stale", None)

    def _path(self, digest: str) -> str:
        return os.path.join(self.root, "objects", digest[:2], digest[2:])
