"""Reassemble the arguments of parallel tool calls that stream on one connection.

The host turns every provider's stream into these events:

    {"type": "call_start", "index": 0, "id": "call_A", "name": "get_weather"}
    {"type": "args_delta", "index": 0, "chunk": '{"city": "Zur'}
    {"type": "call_stop", "index": 0}

index is the call's position in the turn's call list, and every event carries it. Only
call_start carries the id and the name. This is how OpenAI streams tool calls: the id comes
with a call's first fragment, and later fragments are matched by index alone. Fragments of
different calls interleave freely.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field

from .calls import ToolCall

CALL_EVENTS = ("call_start", "args_delta", "call_stop")


@dataclass
class CallBuffer:
    """Everything one call has streamed so far."""

    index: int = -1
    id: str = ""
    name: str = ""
    chunks: list[str] = field(default_factory=list)
    done: bool = False

    def to_call(self) -> ToolCall:
        """The finished call with its arguments parsed. Only valid once call_stop has arrived."""
        if not self.done:
            raise ValueError(f"call {self.index} is still streaming")
        return ToolCall(self.id, self.name, json.loads("".join(self.chunks)))


class StreamAccumulator:
    """One buffer per call, keyed by the call's index."""

    def __init__(self) -> None:
        self.buffers: defaultdict[int, CallBuffer] = defaultdict(CallBuffer)

    def on_event(self, event: dict) -> list[CallBuffer]:
        """Apply one event and return the calls it completed: the call whose call_stop it is.

        Events of other types are left to the caller and complete nothing.
        """
        kind = event["type"]
        if kind not in CALL_EVENTS:
            return []
        buf = self.buffers[event.get("id")]
        if kind == "call_start":
            buf.index, buf.id, buf.name = event["index"], event["id"], event["name"]
        elif kind == "args_delta":
            buf.chunks.append(event["chunk"])
        else:
            buf.done = True
            return [buf]
        return []
