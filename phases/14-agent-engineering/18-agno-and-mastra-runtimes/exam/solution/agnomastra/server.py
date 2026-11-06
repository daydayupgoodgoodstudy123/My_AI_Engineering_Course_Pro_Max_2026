"""A stateless streaming backend: model tokens go out as an HTTP/1.1 chunked response."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing

from .agno import SessionStore

HEADERS = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    b"Transfer-Encoding: chunked\r\n"
    b"\r\n"
)

# model(messages) streams the reply as text tokens; messages are the session history plus "user: <prompt>".
Model = Callable[[list[str]], AsyncIterator[str]]


class StreamingBackend:
    """The streaming request path of a stateless backend.

    The backend keeps no conversation: the history comes from the session store when a request
    starts, and the turns go back to it when the response is complete.
    """

    def __init__(self, store: SessionStore, model: Model) -> None:
        self.store = store
        self.model = model
        self._locks: dict[str, asyncio.Lock] = {}

    async def handle(self, session_id: str, prompt: str) -> AsyncIterator[bytes]:
        """Stream one response as raw HTTP/1.1 bytes: HEADERS, then one chunk per non-empty
        token (its UTF-8 length in hex, CRLF, the bytes, CRLF), then the last chunk "0" CRLF CRLF.

        Each chunk is sent as soon as the model yields its token. Requests for one session run
        one at a time, in the order they start; requests for different sessions run in parallel.
        When the model is done, "user: <prompt>" and "assistant: <reply>" are appended to the
        session before the last chunk goes out. A response the client abandons before its last
        chunk stores nothing and frees its session.
        """
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            yield HEADERS
            messages = self.store.history(session_id) + [f"user: {prompt}"]
            reply: list[str] = []
            async with aclosing(self.model(messages)) as tokens:
                async for token in tokens:
                    data = token.encode("utf-8")
                    if not data:
                        continue
                    reply.append(token)
                    yield b"%x\r\n" % len(data) + data + b"\r\n"
            self.store.append(session_id, f"user: {prompt}")
            self.store.append(session_id, f"assistant: {''.join(reply)}")
            yield b"0\r\n\r\n"
