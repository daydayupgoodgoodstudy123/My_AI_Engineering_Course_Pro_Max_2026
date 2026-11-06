"""Pronunciation lexicon: several pronunciations per word, stored in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


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
        # TODO: create the schema

    def add(self, word: str, phones: list[str], priority: int = 0) -> None:
        """Store one pronunciation of word.

        phones is a non-empty list of segments. A segment that is empty or starts with a
        combining mark (a diacritic with nothing to sit on) raises ValueError, and so does
        a pronunciation the word already has.
        """
        raise NotImplementedError

    def pronunciations(self, word: str) -> list[Pronunciation]:
        """Every pronunciation of word, highest priority first, equal priorities in the
        order they were added. An unknown word has none."""
        raise NotImplementedError

    def best(self, word: str) -> list[str]:
        """Phones of the word's first pronunciation. Unknown words raise KeyError."""
        raise NotImplementedError

    def table(self) -> dict[str, list[str]]:
        """{word: phones of its first pronunciation} for every word, as phonemize takes it."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
