"""Whisper decoder sequences, in the text form a tokenizer prints them.

    <|startofprev|> Earlier text.<|startoftranscript|><|ja|><|transcribe|><|0.00|> こんにちは<|0.58|><|endoftext|>

The prompt names the language spoken in the audio and the task. The output is
timestamped segments or, after <|notimestamps|>, plain text.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SOT = "<|startoftranscript|>"
SOT_PREV = "<|startofprev|>"
EOT = "<|endoftext|>"
NO_TIMESTAMPS = "<|notimestamps|>"
TASKS = ("transcribe", "translate")
LANGUAGES = ("en", "zh", "de", "es", "ru", "ko", "fr", "ja", "is", "ur")  # 10 of Whisper's 99
TIME_PRECISION = 0.02   # one timestamp token every 20 ms
MAX_TIME = 30.0         # timestamp tokens run from <|0.00|> to <|30.00|>


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
    raise NotImplementedError


def parse(text: str) -> Decoding:
    """Read special-token text back into the Decoding that to_text writes for it.

    Raises ValueError for anything to_text would not write: no <|startoftranscript|>,
    unknown tokens, timestamps after <|notimestamps|>, text outside a timestamp pair,
    or a missing <|endoftext|>.
    """
    raise NotImplementedError
