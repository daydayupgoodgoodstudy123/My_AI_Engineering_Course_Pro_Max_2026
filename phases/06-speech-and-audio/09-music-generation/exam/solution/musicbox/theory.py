"""Music theory as data: the lesson's keys, progressions and drum patterns, and chord spelling."""
from __future__ import annotations

PITCH_CLASSES = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}

# The seven triads of each major key, in scale-degree order: I ii iii IV V vi vii°.
MAJOR_KEYS = {
    "C": ["C", "Dm", "Em", "F", "G", "Am", "Bdim"],
    "G": ["G", "Am", "Bm", "C", "D", "Em", "F#dim"],
    "D": ["D", "Em", "F#m", "G", "A", "Bm", "C#dim"],
    "A": ["A", "Bm", "C#m", "D", "E", "F#m", "G#dim"],
}

# Scale degrees, one chord per bar, looped for as many bars as the piece has.
PROGRESSIONS = {
    "pop": [1, 5, 6, 4],
    "ballad": [1, 6, 4, 5],
    "jazz": [2, 5, 1, 6],
    "rock": [1, 4, 5, 1],
    "lofi": [6, 4, 1, 5],
    "baroque": [1, 4, 7, 3, 6, 2, 5, 1],
}

# One bar of sixteenth-note steps: X kick, o snare, x closed hi-hat, . rest.
DRUM_PATTERNS = {
    "pop": "X.o.X.o.X.o.X.o.",
    "rock": "X..oX..oX..oX..o",
    "lofi": "X...o...X...o.o.",
    "jazz": "X.oox.oxX.oox.ox",
    "trap": "Xooox.oxXooox.ox",
}

DRUM_NOTES = {"X": 36, "o": 38, "x": 42}  # General MIDI kick, snare, closed hi-hat

TRIADS = {"": (0, 4, 7), "m": (0, 3, 7), "dim": (0, 3, 6)}


def note_number(name: str, octave: int = 4) -> int:
    """MIDI note number of a pitch name in an octave; middle C (C4) is 60."""
    return 12 * (octave + 1) + PITCH_CLASSES[name]


def chord_tones(symbol: str, octave: int = 4) -> list[int]:
    """Root-position triad, root first, for a chord written as in MAJOR_KEYS: "G", "F#m", "C#dim"."""
    if symbol.endswith("dim"):
        root, quality = symbol[:-3], "dim"
    elif symbol.endswith("m"):
        root, quality = symbol[:-1], "m"
    else:
        root, quality = symbol, ""
    base = note_number(root, octave)
    return [base + interval for interval in TRIADS[quality]]
