"""Follow a call's arguments while they are still streaming.

Parsing the arguments before call_stop raises on a half-written value, and counting braces
is no test of completeness: braces and quotes inside strings, and escapes, fool it.
PartialArguments reads the text as it arrives and tracks its structure instead, so a live UI
can show the arguments that are already final.
"""
from __future__ import annotations


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

    def feed(self, chunk: str) -> None:
        raise NotImplementedError
