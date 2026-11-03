"""Serve the notes server over stdio: newline-delimited JSON-RPC in, the same out."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import BinaryIO

from .protocol import rpc_error
from .server import NotesServer


async def serve_stdio(
    server: NotesServer,
    reader: AsyncIterator[bytes],
    stdout: BinaryIO,
    stderr: BinaryIO,
    principal: str | None = None,
) -> None:
    """Answer newline-delimited JSON-RPC messages until the input ends.

    reader yields stdin as it arrives, in chunks of any size (empty ones too), so a chunk may
    hold part of a line or several lines. Each complete line is one message, and a last line
    without a newline still counts once the input ends. Lines of only whitespace are skipped.

    A line that is not UTF-8 JSON gets a -32700 Parse error, and JSON that is not an object
    (a batch array, a number) gets -32600 Invalid Request, both with a null id; such lines are
    also reported on stderr. Objects go to server.handle(message, principal).

    Each response is written to stdout as one line of compact JSON and flushed right away,
    before the next line is handled or more input is read. stdout carries nothing else.
    Return as soon as the input ends.
    """
    raise NotImplementedError
