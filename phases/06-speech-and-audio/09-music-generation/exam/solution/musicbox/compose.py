"""Prompt -> piece -> notes: the lesson's symbolic generator, rendered on a MIDI-style tick grid."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .theory import DRUM_NOTES, DRUM_PATTERNS, MAJOR_KEYS, PROGRESSIONS, chord_tones

PPQ = 480          # ticks per quarter note, i.e. per beat
STEP = PPQ // 4    # one sixteenth-note step of a drum pattern
BAR = 4 * PPQ      # one bar of 4/4
DRUM_CHANNEL = 9   # General MIDI percussion ("channel 10" in most sequencers)


@dataclass(frozen=True)
class Note:
    start: int         # ticks from the start
    length: int        # ticks
    pitch: int         # MIDI note number
    velocity: int      # 1-127
    channel: int = 0   # MIDI channel, 0-based

    @property
    def end(self) -> int:
        return self.start + self.length


@dataclass(frozen=True)
class Piece:
    key: str
    genre: str
    bpm: int
    chords: list[str]  # one chord per bar
    drums: str         # 16 steps per bar


def detect_key(prompt: str) -> str:
    """The key named after "in", as in "rock anthem in D"; C when no supported key is named."""
    match = re.search(r"\bin ([a-g])\b", prompt.lower())
    key = match.group(1).upper() if match else "C"
    return key if key in MAJOR_KEYS else "C"


def detect_genre(prompt: str) -> str:
    """The first genre in PROGRESSIONS that the prompt mentions; pop otherwise."""
    text = prompt.lower()
    return next((genre for genre in PROGRESSIONS if genre in text), "pop")


def parse_bpm(prompt: str) -> int:
    """The tempo written in the prompt, as "128 bpm", "128bpm" or "128 BPM"; 120 when none is given."""
    match = re.search(r"(\d+)\s*bpm\b", prompt.lower())
    return int(match.group(1)) if match else 120


def compose(prompt: str, bars: int = 8) -> Piece:
    """The lesson's fake_generate: key, genre and tempo from the prompt, one chord per bar."""
    key, genre = detect_key(prompt), detect_genre(prompt)
    degrees = PROGRESSIONS[genre]
    chords = [MAJOR_KEYS[key][degrees[bar % len(degrees)] - 1] for bar in range(bars)]
    drums = DRUM_PATTERNS.get(genre, DRUM_PATTERNS["pop"]) * bars
    return Piece(key, genre, parse_bpm(prompt), chords, drums)


def render(piece: Piece) -> list[Note]:
    """MIDI-style notes for a piece, in the order they start.

    Each bar sounds its chord as a root-position triad (velocity 80) for the whole bar. The
    chords are played legato: a tone that the next chord keeps is held over the bar line
    instead of being struck again. Drum hits (velocity 100, DRUM_CHANNEL) last one step.
    """
    notes: list[Note] = []
    held: dict[int, int] = {}  # pitch -> index of the chord tone that lasts up to this bar line
    for bar, chord in enumerate(piece.chords):
        start = bar * BAR
        sounding: dict[int, int] = {}
        for pitch in chord_tones(chord):
            if pitch in held:
                i = held[pitch]
                notes[i] = replace(notes[i], length=notes[i].length + BAR)
            else:
                i = len(notes)
                notes.append(Note(start, BAR, pitch, 80))
            sounding[pitch] = i
        held = sounding
        pattern = piece.drums[bar * 16 : (bar + 1) * 16]
        for step, hit in enumerate(pattern):
            if hit != ".":
                notes.append(Note(start + step * STEP, STEP, DRUM_NOTES[hit], 100, DRUM_CHANNEL))
    return notes


def seconds(piece: Piece, tick: int) -> float:
    """Seconds from the start of the piece to tick: tick / PPQ beats of 60 / bpm seconds each."""
    return tick * 60 / (PPQ * piece.bpm)
