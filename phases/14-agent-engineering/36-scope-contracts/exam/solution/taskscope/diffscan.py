"""Check a streaming `git diff` against a scope contract and report SARIF results."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from urllib.parse import quote

from .check import Classifier
from .contract import ScopeContract

RULES = {
    "forbidden": ("scope/forbidden", "error", "{path} is forbidden by the contract"),
    "off_scope": ("scope/off-scope", "warning", "{path} is outside allowed_files"),
    "soft": ("scope/soft-off-scope", "note", "{path} is a docs path outside allowed_files"),
}
MOVES = (b"rename from ", b"rename to ", b"copy from ", b"copy to ")
C_ESCAPES = {ord("a"): 7, ord("b"): 8, ord("t"): 9, ord("n"): 10, ord("v"): 11, ord("f"): 12, ord("r"): 13}


async def scan_diff(chunks: AsyncIterator[bytes], contract: ScopeContract) -> AsyncIterator[str]:
    """Check a `git diff` against the contract while it streams in.

    chunks is the raw output of `git diff`, bytes cut at arbitrary points; the stream
    may end without a final newline, and hunk lines may hold any bytes at all. Every
    file the diff writes is checked: a modified, added or deleted file, a file whose
    mode changed, a binary file, both sides of a rename, and the destination of a
    copy (a copy leaves its source as it was). Each path is reported at most once, as
    soon as its file header is complete: at the file's first hunk ("@@"), at the next
    "diff --git", or at the end of the stream.

    git writes paths in the "diff --git a/<path> b/<path>" line and, for a rename or a
    copy, in "rename from <path>" and "rename to <path>" (or "copy from" and "copy to")
    lines. A path with a double quote, a backslash, a control character or a non-ASCII
    byte is written in double quotes with C escapes (\\", \\\\, \\t, \\n, and \\ooo octal
    for each byte of its UTF-8 name). Any other path, spaces included, is written as is.

    Yields one line of JSON per finding, shaped like a SARIF result:
        {"ruleId": ..., "level": ..., "message": {"text": ...},
         "locations": [{"physicalLocation": {"artifactLocation": {"uri": ...}}}]}
    ruleId and level are "scope/forbidden" and "error", "scope/off-scope" and
    "warning", or "scope/soft-off-scope" and "note"; an in-scope path yields nothing.
    message.text names the path, and uri is the path as a relative URI reference
    (urllib.parse.quote). When the distinct off-scope files first outnumber the
    contract's violation_budget, a "scope/over-budget" result (level "error") for the
    file that tipped it follows that file's own result.
    """
    classifier = Classifier(contract)
    seen: set[str] = set()
    off_scope = 0
    header: list[bytes] | None = None

    def finish(lines: list[bytes]) -> list[str]:
        nonlocal off_scope
        results = []
        for path in _paths(lines):
            if path in seen:
                continue
            seen.add(path)
            kind = classifier.classify(path)
            if kind == "in_scope":
                continue
            rule, level, text = RULES[kind]
            results.append(_result(rule, level, text.format(path=path), path))
            if kind == "off_scope":
                off_scope += 1
                if off_scope == contract.violation_budget + 1:
                    results.append(_result(
                        "scope/over-budget", "error",
                        f"{off_scope} off-scope files exceed the violation budget of {contract.violation_budget}",
                        path,
                    ))
        return results

    def feed(line: bytes) -> list[str]:
        nonlocal header
        if line.startswith(b"diff --git "):
            done = finish(header) if header is not None else []
            header = [line]
            return done
        if header is None:
            return []
        if line.startswith(b"@@"):
            done, header = finish(header), None
            return done
        header.append(line)
        return []

    buffer = bytearray()
    async for chunk in chunks:
        buffer += chunk
        start = 0
        while (end := buffer.find(b"\n", start)) != -1:
            for result in feed(bytes(buffer[start:end])):
                yield result
            start = end + 1
        del buffer[:start]
    if buffer:
        for result in feed(bytes(buffer)):
            yield result
    if header is not None:
        for result in finish(header):
            yield result


def _paths(header: list[bytes]) -> list[str]:
    """The paths one file header writes."""
    moves: dict[bytes, str] = {}
    for line in header[1:]:
        for key in MOVES:
            if line.startswith(key):
                moves[key] = _name(line[len(key):])
    if b"rename from " in moves and b"rename to " in moves:
        return [moves[b"rename from "], moves[b"rename to "]]
    if b"copy to " in moves:
        return [moves[b"copy to "]]
    return [_header_name(header[0][len(b"diff --git "):])]


def _header_name(rest: bytes) -> str:
    """The path in 'a/<path> b/<path>' when both sides name the same file."""
    if rest.startswith(b'"'):
        name, _ = _unquote(rest)
        return _decode(name[2:] if name.startswith(b"a/") else name)
    size, odd = divmod(len(rest) - 5, 2)
    if not odd and size > 0 and rest.startswith(b"a/") and rest[2 + size:5 + size] == b" b/":
        if rest[2:2 + size] == rest[5 + size:]:
            return _decode(rest[2:2 + size])
    left = rest.rsplit(b" b/", 1)[0]
    return _decode(left[2:] if left.startswith(b"a/") else left)


def _name(raw: bytes) -> str:
    return _decode(_unquote(raw)[0] if raw.startswith(b'"') else raw)


def _unquote(raw: bytes) -> tuple[bytes, int]:
    """A C-quoted name starting at raw[0] == '"': its bytes, and the index after it."""
    out = bytearray()
    i = 1
    while i < len(raw):
        c = raw[i]
        if c == ord('"'):
            return bytes(out), i + 1
        if c == ord("\\") and i + 1 < len(raw):
            d = raw[i + 1]
            if ord("0") <= d <= ord("7"):
                out.append(int(raw[i + 1:i + 4], 8) & 0xFF)
                i += 4
                continue
            out.append(C_ESCAPES.get(d, d))
            i += 2
            continue
        out.append(c)
        i += 1
    raise ValueError(f"unterminated quoted name: {raw!r}")


def _decode(name: bytes) -> str:
    return name.decode("utf-8", "surrogateescape")


def _result(rule: str, level: str, text: str, path: str) -> str:
    uri = quote(path, errors="surrogateescape")
    return json.dumps({
        "ruleId": rule,
        "level": level,
        "message": {"text": text},
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": uri}}}],
    }) + "\n"
