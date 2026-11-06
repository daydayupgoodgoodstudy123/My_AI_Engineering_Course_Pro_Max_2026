"""Carry messages between runtimes on different hosts over a byte stream.

Inbox + transport is the same abstraction whether the actor is in-process or on another host. A
Link registers a RemoteActor for each actor that lives on the other host. Whatever a RemoteActor
receives goes out on the link as a frame, and Link.serve() delivers the frames that come in like
any other message.

A frame is the 4-byte big-endian length of its payload, then the payload: a UTF-8 JSON object with
the keys mid, sender, recipient, topic and body. Non-ASCII text goes as UTF-8, not as \\u escapes,
so frames of CJK text stay small. A frame of length 0 is a heartbeat and carries no message.
"""
from __future__ import annotations

import json
import struct
from collections import deque
from collections.abc import AsyncIterator, Iterable, Iterator

from .runtime import Actor, Message, Runtime

LENGTH = struct.Struct(">I")


def encode_frame(message: Message) -> bytes:
    """The frame for one message. Its mid is the sending host's mid."""
    payload = json.dumps(
        {
            "mid": message.mid,
            "sender": message.sender,
            "recipient": message.recipient,
            "topic": message.topic,
            "body": message.body,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    return LENGTH.pack(len(payload)) + payload


class FrameReader:
    """Reassembles frames from a byte stream that arrives in chunks of any size."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> None:
        """Add the next chunk of the stream."""
        self._buffer += chunk

    def __iter__(self) -> Iterator[dict]:
        """Take each complete frame off the buffer, in order, and yield its message fields.

        Heartbeats are skipped. A payload that is not a JSON object with string sender, recipient
        and topic and a body raises ValueError when its frame is reached.
        """
        while len(self._buffer) >= LENGTH.size:
            (size,) = LENGTH.unpack_from(self._buffer)
            end = LENGTH.size + size
            if len(self._buffer) < end:
                return
            payload = bytes(self._buffer[LENGTH.size : end])
            del self._buffer[:end]
            if size:
                yield _fields(payload)

    def close(self) -> None:
        """The stream has ended. Bytes left over mean it ended inside a frame: ValueError."""
        if self._buffer:
            raise ValueError(f"the stream ended inside a frame, {len(self._buffer)} bytes in")


def _fields(payload: bytes) -> dict:
    fields = json.loads(payload.decode("utf-8"))
    if not isinstance(fields, dict) or "body" not in fields:
        raise ValueError("a frame carries a JSON object with a body")
    for key in ("sender", "recipient", "topic"):
        if not isinstance(fields.get(key), str):
            raise ValueError(f"a frame's {key} must be a string")
    return fields


class RemoteActor(Actor):
    """Stands in for an actor on the other host: what it receives goes out on the link."""

    def __init__(self, name: str, link: Link) -> None:
        super().__init__(name)
        self.link = link

    def receive(self, message: Message, runtime: Runtime) -> None:
        self.link.write(encode_frame(message))


class Link:
    """One host's end of the byte stream to another host."""

    def __init__(self, runtime: Runtime, remote: Iterable[str]) -> None:
        """Register a RemoteActor on runtime for every actor that lives on the other host."""
        self.runtime = runtime
        self._out: deque[bytes] = deque()
        for name in remote:
            runtime.register(RemoteActor(name, self))

    def write(self, frame: bytes) -> None:
        self._out.append(frame)

    def take(self) -> list[bytes]:
        """Remove and return the frames written so far, oldest first."""
        frames = list(self._out)
        self._out.clear()
        return frames

    async def serve(self, chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        """Deliver the frames that arrive on chunks, and yield the frames written meanwhile.

        Frames already waiting on the link come out first. Each arriving message is queued with
        runtime.send() (it gets a mid of this host) and handled with runtime.run_until_idle()
        before the next frame is read, and every frame written meanwhile is yielded at once, one
        frame per item. If the stream ends inside a frame, or a frame is malformed, ValueError is
        raised once the frames before it have been delivered.
        """
        for frame in self.take():
            yield frame
        reader = FrameReader()
        async for chunk in chunks:
            reader.feed(chunk)
            for fields in reader:
                self.runtime.send(fields["sender"], fields["recipient"], fields["topic"], fields["body"])
                self.runtime.run_until_idle()
                for frame in self.take():
                    yield frame
        reader.close()
