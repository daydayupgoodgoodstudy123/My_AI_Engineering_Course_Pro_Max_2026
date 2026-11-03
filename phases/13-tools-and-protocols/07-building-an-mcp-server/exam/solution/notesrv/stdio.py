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
    pending = bytearray()
    async for chunk in reader:
        pending += chunk
        start = 0
        while (end := pending.find(b"\n", start)) != -1:
            _answer(server, bytes(pending[start:end]), stdout, stderr, principal)
            start = end + 1
        del pending[:start]
    if pending:
        _answer(server, bytes(pending), stdout, stderr, principal)


def _answer(server: NotesServer, line: bytes, stdout: BinaryIO, stderr: BinaryIO, principal: str | None) -> None:
    if not line.strip():
        return
    try:
        message = json.loads(line.decode("utf-8"))
    except ValueError as exc:  # UnicodeDecodeError and JSONDecodeError are both ValueErrors
        _report(stderr, f"parse error: {exc}")
        response = rpc_error(None, -32700, "Parse error")
    else:
        if isinstance(message, dict):
            response = server.handle(message, principal)
        else:
            _report(stderr, f"expected a JSON-RPC object, got {type(message).__name__}")
            response = rpc_error(None, -32600, "Invalid Request")
    if response is not None:
        stdout.write(json.dumps(response, separators=(",", ":")).encode("utf-8") + b"\n")
        stdout.flush()


def _report(stderr: BinaryIO, text: str) -> None:
    stderr.write(f"notesrv: {text}\n".encode("utf-8"))
    stderr.flush()
