"""The inner monologue: the model's words, laid onto its 12.5 Hz text stream."""
from __future__ import annotations

from dataclasses import dataclass

from .mimi import FRAME_MS
from .tokens import EPAD, PAD


@dataclass(frozen=True)
class Word:
    """One word the model says: its text tokens (at least one), and when it starts in seconds
    from the start of the session, as a forced aligner reports it (millisecond resolution)."""

    tokens: list[int]
    start: float


def align(words: list[Word], n_frames: int) -> list[int]:
    """Lay timed words onto the text stream, one token per 80 ms frame.

    Frame t covers [t * 80 ms, (t + 1) * 80 ms). A word's first token goes in the frame that holds
    its start time and its other tokens in the frames right after it. The frame just before a
    word's first token holds EPAD, which announces the word; every other frame holds PAD. Words
    never overwrite each other: a word that would land on the one before it, or leave no free
    frame for its EPAD, moves to the first frame where it fits.

    Words must come in time order and fit in n_frames frames; anything else raises ValueError.
    """
    stream = [PAD] * n_frames
    free = 0  # first frame that no earlier word uses
    previous_ms = 0
    for word in words:
        if not word.tokens:
            raise ValueError("a word needs at least one token")
        ms = round(word.start * 1000)
        if ms < previous_ms:
            raise ValueError(f"words must come in time order from 0 s, got one at {word.start} s")
        previous_ms = ms
        first = max(ms // FRAME_MS, free + 1)
        end = first + len(word.tokens)
        if end > n_frames:
            raise ValueError(f"the words need {end} frames, the stream has {n_frames}")
        stream[first - 1] = EPAD
        stream[first:end] = word.tokens
        free = end
    return stream


def transcript(stream: list[int]) -> list[tuple[int, list[int]]]:
    """Read the words back off a text stream: (frame of the first token, tokens) for each word.

    Each EPAD announces a word whose tokens fill the frames after it, up to the next PAD or EPAD.
    """
    words: list[tuple[int, list[int]]] = []
    current: list[int] | None = None
    for t, token in enumerate(stream):
        if token == EPAD:
            current = []
            words.append((t + 1, current))
        elif token == PAD:
            current = None
        elif current is None:
            raise ValueError(f"frame {t} holds a token that no EPAD announced")
        else:
            current.append(token)
    if any(not tokens for _, tokens in words):
        raise ValueError("an EPAD announces a word with no tokens")
    return words
