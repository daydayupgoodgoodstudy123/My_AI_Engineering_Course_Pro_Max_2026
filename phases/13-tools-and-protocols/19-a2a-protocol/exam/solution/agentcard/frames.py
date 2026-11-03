"""A length-prefixed frame binding for streamed tasks.

The lesson's default binding is JSON-RPC over HTTP, with SSE for streaming; its second binding is gRPC.
This harness stands in for the second one with framing of its own, which is not gRPC's wire format:
every frame is a 4-byte big-endian unsigned length, then exactly that many bytes of UTF-8 JSON holding
one event. The length counts the JSON bytes only, not the 4 bytes of the length itself.

Events:
  {"kind": "status", "taskId": id, "state": state, "final": true or false}
      the task moved to a new state; a status can also carry "message", the agent's text.
  {"kind": "artifact", "taskId": id, "name": name, "seq": n, "text": piece}
      the next piece of an artifact's text; seq counts that artifact's pieces from 0.
A stream ends with its one final status, and nothing follows it.
"""
from __future__ import annotations

import json
import struct
from collections.abc import AsyncIterator

from .model import Artifact, Task, text_part

MAX_FRAME = 1 << 20  # the most JSON bytes one frame may carry


class ModelError(Exception):
    """The model behind the writer failed."""


def encode_frame(event: dict) -> bytes:
    """One event as a frame. An event whose JSON is longer than MAX_FRAME bytes raises ValueError."""
    body = json.dumps(event).encode("utf-8")
    if len(body) > MAX_FRAME:
        raise ValueError(f"a frame of {len(body)} bytes is over the {MAX_FRAME}-byte limit")
    return struct.pack(">I", len(body)) + body


class FrameReader:
    """Turns a stream's bytes back into events, whatever sizes the chunks arrive in.

    feed() returns the events whose frames are now complete, in order, and keeps a partial frame for
    the next call. It raises ValueError as soon as a length is over MAX_FRAME (without waiting for the
    body), an artifact piece is not the next seq for its artifact, or any byte arrives after the final
    status. close() raises ValueError if the stream stopped inside a frame or before its final status.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._next_seq: dict[str, int] = {}
        self._final = False

    def feed(self, data: bytes) -> list[dict]:
        if self._final and data:
            raise ValueError("bytes arrived after the final status")
        self._buffer += data
        events = []
        while len(self._buffer) >= 4:
            (length,) = struct.unpack(">I", self._buffer[:4])
            if length > MAX_FRAME:
                raise ValueError(f"a frame of {length} bytes is over the {MAX_FRAME}-byte limit")
            if len(self._buffer) < 4 + length:
                break
            event = json.loads(bytes(self._buffer[4 : 4 + length]).decode("utf-8"))
            del self._buffer[: 4 + length]
            self._check(event)
            events.append(event)
            if self._final and self._buffer:
                raise ValueError("bytes arrived after the final status")
        return events

    def _check(self, event: dict) -> None:
        if event.get("kind") == "artifact":
            expected = self._next_seq.get(event["name"], 0)
            if event["seq"] != expected:
                raise ValueError(
                    f"piece {event['seq']} of {event['name']!r} arrived where {expected} was next"
                )
            self._next_seq[event["name"]] = expected + 1
        elif event.get("kind") == "status" and event.get("final"):
            self._final = True

    def close(self) -> None:
        if self._buffer:
            raise ValueError("the stream stopped inside a frame")
        if not self._final:
            raise ValueError("the stream stopped before its final status")


async def stream_task(
    task: Task, pieces: AsyncIterator[str], artifact: str = "report"
) -> AsyncIterator[bytes]:
    """Run a submitted task whose artifact the model writes piece by piece, and stream it as frames.

    Every frame is yielded on its own, as soon as it is ready:
      - a status frame for working, once the task has moved to working and before the model is asked
        for anything;
      - an artifact frame for every piece that isn't empty, numbered from 0;
      - a final status frame for completed, once the task has completed with the whole text as its
        artifact (named artifact, mimeType text/markdown, one text part).
    If the model raises ModelError, the stream ends with a final status frame for failed whose message
    is the error's text, and the task fails without an artifact. If the caller closes the stream before
    the end, the model's stream is closed at once and the task is canceled.
    """
    task.move("working")
    text: list[str] = []
    try:
        yield encode_frame({"kind": "status", "taskId": task.id, "state": "working", "final": False})
        async for piece in pieces:
            if not piece:
                continue
            frame = {"kind": "artifact", "taskId": task.id, "name": artifact, "seq": len(text), "text": piece}
            text.append(piece)
            yield encode_frame(frame)
    except ModelError as error:
        task.move("failed")
        yield encode_frame(
            {"kind": "status", "taskId": task.id, "state": "failed", "final": True, "message": str(error)}
        )
        return
    except GeneratorExit:
        task.move("canceled")
        close = getattr(pieces, "aclose", None)
        if close is not None:
            await close()
        raise
    task.artifact = Artifact(artifact, "text/markdown", [text_part("".join(text))])
    task.move("completed")
    yield encode_frame({"kind": "status", "taskId": task.id, "state": "completed", "final": True})
