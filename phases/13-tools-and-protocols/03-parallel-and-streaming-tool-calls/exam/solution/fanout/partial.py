"""Follow a call's arguments while they are still streaming.

Parsing the arguments before call_stop raises on a half-written value, and counting braces
is no test of completeness: braces and quotes inside strings, and escapes, fool it.
PartialArguments reads the text as it arrives and tracks its structure instead, so a live UI
can show the arguments that are already final.
"""
from __future__ import annotations

import json

WHITESPACE = " \t\n\r"
CLOSER = {"{": "}", "[": "]"}


class PartialArguments:
    """A call's arguments text, fed in chunks of any size. Arguments are always a JSON object.

    complete is True once the whole object has arrived; after that only whitespace may follow.
    members holds the top-level members whose values are complete, decoded. A member is there
    by the time the comma or brace after it arrives, and never while its value can still grow.

    feed raises ValueError as soon as the text cannot be the start of a JSON object: a value
    that is not an object, a bracket closed by the wrong partner, anything but whitespace after
    the object. A mistake inside a member is reported by the comma or brace that ends the member,
    if not earlier.
    """

    def __init__(self) -> None:
        self.complete = False
        self.members: dict = {}
        self._stack: list[str] = []  # open brackets, outermost first
        self._member: list[str] = []  # text of the top-level member being read
        self._in_string = False
        self._escaped = False

    def feed(self, chunk: str) -> None:
        for ch in chunk:
            self._step(ch)

    def _step(self, ch: str) -> None:
        if self.complete:
            if ch not in WHITESPACE:
                raise ValueError(f"{ch!r} after the end of the arguments")
            return
        if self._in_string:
            if self._escaped:
                self._escaped = False
            elif ch == "\\":
                self._escaped = True
            elif ch == '"':
                self._in_string = False
            self._member.append(ch)
            return
        if not self._stack:
            if ch in WHITESPACE:
                return
            if ch != "{":
                raise ValueError(f"arguments must be a JSON object, got {ch!r}")
            self._stack.append(ch)
            return
        if ch == '"':
            self._in_string = True
        elif ch in CLOSER:
            self._stack.append(ch)
        elif ch in "]}":
            if CLOSER[self._stack[-1]] != ch:
                raise ValueError(f"{ch!r} cannot close {self._stack[-1]!r}")
            self._stack.pop()
            if not self._stack:
                self._end_member(closing=True)
                self.complete = True
                return
        elif ch == "," and len(self._stack) == 1:
            self._end_member(closing=False)
            return
        self._member.append(ch)

    def _end_member(self, closing: bool) -> None:
        text = "".join(self._member).strip()
        self._member = []
        if not text:
            if closing and not self.members:
                return  # "{}"
            raise ValueError("missing member: a stray or trailing comma")
        self.members.update(json.loads("{" + text + "}"))
