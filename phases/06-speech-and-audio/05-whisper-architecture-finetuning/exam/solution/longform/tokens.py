"""Whisper decoder sequences, in the text form a tokenizer prints them.

    <|startofprev|> Earlier text.<|startoftranscript|><|ja|><|transcribe|><|0.00|> こんにちは<|0.58|><|endoftext|>

The prompt names the language spoken in the audio and the task. The output is
timestamped segments or, after <|notimestamps|>, plain text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SOT = "<|startoftranscript|>"
SOT_PREV = "<|startofprev|>"
EOT = "<|endoftext|>"
NO_TIMESTAMPS = "<|notimestamps|>"
TASKS = ("transcribe", "translate")
LANGUAGES = ("en", "zh", "de", "es", "ru", "ko", "fr", "ja", "is", "ur")  # 10 of Whisper's 99
TIME_PRECISION = 0.02   # one timestamp token every 20 ms
MAX_TIME = 30.0         # timestamp tokens run from <|0.00|> to <|30.00|>

_SPECIAL = re.compile(r"(<\|[^<>|]*\|>)")
_TIMESTAMP = re.compile(r"<\|(\d+\.\d\d)\|>")
_MAX_TICK = round(MAX_TIME / TIME_PRECISION)


@dataclass(frozen=True)
class Segment:
    """Text between two timestamp tokens, timed in seconds."""

    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Decoding:
    """One window's decoder sequence.

    language is the language spoken in the audio; task is "transcribe", or "translate"
    into English. With timestamps the output is segments, timed from the start of the
    window. With timestamps off, text holds the output and segments stays empty.
    previous is earlier transcript fed back after <|startofprev|>, or None.
    """

    language: str
    task: str = "transcribe"
    segments: list[Segment] = field(default_factory=list)
    text: str | None = None
    previous: str | None = None


def to_text(decoding: Decoding) -> str:
    """Write a decoding as special-token text.

    Text is copied as it is, leading spaces included. Timestamp tokens carry two decimals
    (<|1.10|>) and must sit on the 0.02 s grid from 0 to 30 s; segments run in order and
    do not overlap. An unknown language or task, text containing "<|" or "|>", or a
    decoding with both segments and text raises ValueError.
    """
    if decoding.language not in LANGUAGES:
        raise ValueError(f"unknown language {decoding.language!r}")
    if decoding.task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}, got {decoding.task!r}")
    if decoding.segments and decoding.text is not None:
        raise ValueError("a decoding holds timestamped segments or plain text, not both")
    parts: list[str] = []
    if decoding.previous is not None:
        parts += [SOT_PREV, _plain(decoding.previous)]
    parts += [SOT, f"<|{decoding.language}|>", f"<|{decoding.task}|>"]
    if decoding.text is not None:
        parts += [NO_TIMESTAMPS, _plain(decoding.text)]
    last = 0
    for segment in decoding.segments:
        start, end = _tick(segment.start), _tick(segment.end)
        if not last <= start <= end:
            raise ValueError(f"segments must run in order without overlapping: {segment}")
        parts += [_token(start), _plain(segment.text), _token(end)]
        last = end
    parts.append(EOT)
    return "".join(parts)


def parse(text: str) -> Decoding:
    """Read special-token text back into the Decoding that to_text writes for it.

    Raises ValueError for anything to_text would not write: no <|startoftranscript|>,
    unknown tokens, timestamps after <|notimestamps|>, text outside a timestamp pair,
    or a missing <|endoftext|>.
    """
    items = [piece for piece in _SPECIAL.split(text) if piece]
    items.reverse()

    def special() -> str:
        if not items or not _SPECIAL.fullmatch(items[-1]):
            raise ValueError(f"expected a special token, got {items[-1:]}")
        return items.pop()

    def plain() -> str:
        return items.pop() if items and not _SPECIAL.fullmatch(items[-1]) else ""

    previous = None
    token = special()
    if token == SOT_PREV:
        previous = plain()
        token = special()
    if token != SOT:
        raise ValueError(f"a decoding starts with {SOT}, got {token}")
    language, task = special()[2:-2], special()[2:-2]
    token = special()
    if token == NO_TIMESTAMPS:
        decoding = Decoding(language, task, text=plain(), previous=previous)
        token = special()
    else:
        segments = []
        while token != EOT:
            start, body, end = _seconds(token), plain(), _seconds(special())
            segments.append(Segment(start, end, body))
            token = special()
        decoding = Decoding(language, task, segments, previous=previous)
    if token != EOT or items:
        raise ValueError(f"a decoding ends with {EOT}")
    if to_text(decoding) != text:
        raise ValueError("not the text to_text writes for this decoding")
    return decoding


def _plain(text: str) -> str:
    if "<|" in text or "|>" in text:
        raise ValueError(f"text cannot contain special-token markers: {text!r}")
    return text


def _tick(seconds: float) -> int:
    tick = round(seconds / TIME_PRECISION)
    if not 0 <= tick <= _MAX_TICK or abs(seconds - tick * TIME_PRECISION) > 1e-9:
        raise ValueError(f"timestamp {seconds!r} is not on the 0.02 s grid from 0 to 30 s")
    return tick


def _token(tick: int) -> str:
    return f"<|{tick * TIME_PRECISION:.2f}|>"


def _seconds(token: str) -> float:
    match = _TIMESTAMP.fullmatch(token)
    if match is None:
        raise ValueError(f"expected a timestamp token, got {token}")
    seconds = float(match.group(1))
    _tick(seconds)
    return seconds
