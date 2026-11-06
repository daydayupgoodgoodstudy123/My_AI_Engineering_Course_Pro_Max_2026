"""Cut streaming LLM text into chunks the synthesizer can start on early."""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from .normalize import ABBREVIATIONS

_WORD_BEFORE = re.compile(r"([A-Za-z]+)$")


async def speech_events(deltas: AsyncIterator[str], min_chars: int = 20) -> AsyncIterator[str]:
    """Send each speakable chunk of the text as soon as it is complete.

    Deltas are pieces of text of any size, as an LLM streams them. A chunk ends after
    . ? or ! followed by whitespace, or after , ; or : followed by whitespace once the
    chunk is at least min_chars long. A period right after an abbreviation (Dr.) does not
    end a chunk. What is left when the stream ends is the last chunk. Chunks are sent
    stripped, and an empty chunk is not sent.

    Each chunk is one server-sent event: "data: " + JSON {"seq": n, "text": chunk},
    followed by a blank line. seq counts from 0.
    """
    buffer = ""
    seq = 0
    async for delta in deltas:
        buffer += delta
        while (cut := _first_cut(buffer, min_chars)) is not None:
            chunk, buffer = buffer[:cut].strip(), buffer[cut:]
            if chunk:
                yield _event(seq, chunk)
                seq += 1
    rest = buffer.strip()
    if rest:
        yield _event(seq, rest)


def _first_cut(text: str, min_chars: int) -> int | None:
    """Index just past the first mark that ends a chunk, or None if none is decided yet."""
    # The last character has nothing after it yet, so a mark there waits for more text.
    for j in range(len(text) - 1):
        mark = text[j]
        if not text[j + 1].isspace():
            continue
        if mark in ".?!":
            if mark == "." and _after_abbreviation(text, j):
                continue
            return j + 1
        if mark in ",;:" and len(text[: j + 1].strip()) >= min_chars:
            return j + 1
    return None


def _after_abbreviation(text: str, j: int) -> bool:
    word = _WORD_BEFORE.search(text, 0, j)
    return word is not None and word.group(1).lower() in ABBREVIATIONS


def _event(seq: int, text: str) -> str:
    return "data: " + json.dumps({"seq": seq, "text": text}) + "\n\n"
