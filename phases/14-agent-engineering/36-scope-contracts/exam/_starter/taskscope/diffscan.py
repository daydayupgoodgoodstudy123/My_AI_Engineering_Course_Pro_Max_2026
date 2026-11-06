"""Check a streaming `git diff` against a scope contract and report SARIF results."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .contract import ScopeContract


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
    raise NotImplementedError
