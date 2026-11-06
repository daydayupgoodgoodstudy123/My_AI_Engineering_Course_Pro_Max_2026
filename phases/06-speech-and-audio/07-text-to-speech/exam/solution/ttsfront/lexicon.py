"""Pronunciation lexicon: several pronunciations per word, stored in SQLite."""
from __future__ import annotations

import json
import sqlite3
import unicodedata
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS pronunciations (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    phones TEXT NOT NULL,
    priority INTEGER NOT NULL
)
"""


@dataclass(frozen=True)
class Pronunciation:
    word: str
    phones: list[str]
    priority: int


class PronunciationLexicon:
    """Words and their pronunciations.

    A word may have several pronunciations, and a higher priority is preferred. Words
    match ignoring case and are reported in lowercase. Phones are kept exactly as given,
    in whatever alphabet the caller uses: ARPAbet, or IPA with combining marks and tie bars.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.execute(SCHEMA)

    def add(self, word: str, phones: list[str], priority: int = 0) -> None:
        """Store one pronunciation of word.

        phones is a non-empty list of segments. A segment that is empty or starts with a
        combining mark (a diacritic with nothing to sit on) raises ValueError, and so does
        a pronunciation the word already has.
        """
        key = word.lower()
        if not key:
            raise ValueError("a pronunciation needs a word")
        if not phones:
            raise ValueError(f"{word!r} needs at least one phone")
        for segment in phones:
            if not isinstance(segment, str) or not segment:
                raise ValueError(f"empty or non-text segment in {phones!r}")
            if unicodedata.category(segment[0]).startswith("M"):
                raise ValueError(f"segment {segment!r} starts with a combining mark")
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an integer, got {priority!r}")
        encoded = json.dumps(list(phones))
        duplicate = self._db.execute(
            "SELECT 1 FROM pronunciations WHERE word = ? AND phones = ?", (key, encoded)
        ).fetchone()
        if duplicate:
            raise ValueError(f"{word!r} already has the pronunciation {phones!r}")
        with self._db:
            self._db.execute(
                "INSERT INTO pronunciations (word, phones, priority) VALUES (?, ?, ?)",
                (key, encoded, priority),
            )

    def pronunciations(self, word: str) -> list[Pronunciation]:
        """Every pronunciation of word, highest priority first, equal priorities in the
        order they were added. An unknown word has none."""
        rows = self._db.execute(
            "SELECT word, phones, priority FROM pronunciations WHERE word = ?"
            " ORDER BY priority DESC, seq",
            (word.lower(),),
        )
        return [Pronunciation(w, json.loads(phones), priority) for w, phones, priority in rows]

    def best(self, word: str) -> list[str]:
        """Phones of the word's first pronunciation. Unknown words raise KeyError."""
        found = self.pronunciations(word)
        if not found:
            raise KeyError(word)
        return found[0].phones

    def table(self) -> dict[str, list[str]]:
        """{word: phones of its first pronunciation} for every word, as phonemize takes it."""
        best: dict[str, list[str]] = {}
        rows = self._db.execute(
            "SELECT word, phones FROM pronunciations ORDER BY word, priority DESC, seq"
        )
        for word, phones in rows:
            best.setdefault(word, json.loads(phones))
        return best

    def close(self) -> None:
        self._db.close()
