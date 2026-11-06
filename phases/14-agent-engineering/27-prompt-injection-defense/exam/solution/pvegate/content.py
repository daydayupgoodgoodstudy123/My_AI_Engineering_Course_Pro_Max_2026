"""Where each piece of context came from, and the directive detector every check shares."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# Most trusted first. Only user_message carries the user's own instructions.
SOURCES = ("user_message", "tool_output", "retrieved")


@dataclass(frozen=True)
class Content:
    """One piece of the agent's context, tagged with its source.

    tainted says whether the text may carry someone other than the user's words. It defaults
    to True for every source except user_message.
    """

    text: str
    source: str
    tainted: bool | None = None

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise ValueError(f"unknown source {self.source!r}, expected one of {SOURCES}")
        if self.tainted is None:
            object.__setattr__(self, "tainted", self.source != "user_message")


INJECTION_MARKERS = (
    "ignore all instructions", "ignore previous instructions",
    "system:", "override:", "act as the",
    "send the conversation to", "exfiltrate",
    "forward to http", "rm -rf", "drop table",
)

# Characters that render as nothing: soft hyphen, zero-width space, non-joiner and joiner,
# word joiner, byte order mark, and the Unicode tag block.
INVISIBLE = frozenset("\u00ad\u200b\u200c\u200d\u2060\ufeff") | frozenset(
    chr(c) for c in range(0xE0000, 0xE0080)
)


def _drop_invisible(text: str) -> str:
    """text without the characters in INVISIBLE."""
    return "".join(ch for ch in text if ch not in INVISIBLE)


def normalize(text: str) -> str:
    """The form directives are matched in: NFKC, INVISIBLE characters removed, casefolded, stripped.

    For detection only. Tools and storage get the original text.
    """
    return _drop_invisible(unicodedata.normalize("NFKC", text)).casefold().strip()


def looks_like_directive(text: str) -> str | None:
    """The first INJECTION_MARKERS entry found in normalize(text), "starts with do/execute"
    when the normalized text opens with the word do or execute, otherwise None."""
    t = normalize(text)
    for marker in INJECTION_MARKERS:
        if marker in t:
            return marker
    if t.startswith("do ") or t.startswith("execute "):
        return "starts with do/execute"
    return None
