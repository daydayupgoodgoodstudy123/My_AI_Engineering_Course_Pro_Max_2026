"""Reference transcripts and model hypotheses, stored in SQLite."""
from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS utterances (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    utt_id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hypotheses (
    utt_id TEXT NOT NULL,
    model TEXT NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (utt_id, model)
);
"""


@dataclass(frozen=True)
class Utterance:
    utt_id: str
    reference: str
    hypotheses: dict[str, str]  # model version -> what it transcribed


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


class TranscriptStore:
    """Reference transcripts, and what every model version transcribed for each utterance.

    Ids, model names and transcripts are kept in Unicode NFC, so text that looks the same
    is the same: an id taken from a macOS file name (usually decomposed) finds the utterance
    loaded from a spreadsheet. Nothing else about the text changes. Case, punctuation,
    spacing and compatibility characters such as ² or ﬁ are kept exactly; normalizing
    for WER is the scorer's job.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        with self._db:
            self._db.executescript(SCHEMA)

    def add_utterance(self, utt_id: str, reference: str) -> None:
        """Register an utterance with its reference transcript. A known id raises ValueError."""
        utt_id = nfc(utt_id)
        if self._reference(utt_id) is not None:
            raise ValueError(f"utterance {utt_id!r} already exists")
        with self._db:
            self._db.execute(
                "INSERT INTO utterances (utt_id, reference) VALUES (?, ?)", (utt_id, nfc(reference))
            )

    def add_hypothesis(self, utt_id: str, model: str, text: str) -> None:
        """Record what one model version transcribed for an utterance.

        Unknown utterances raise KeyError. A model version never changes its mind:
        recording the same transcript again does nothing, a different one raises ValueError.
        """
        utt_id, model, text = nfc(utt_id), nfc(model), nfc(text)
        if self._reference(utt_id) is None:
            raise KeyError(utt_id)
        row = self._db.execute(
            "SELECT text FROM hypotheses WHERE utt_id = ? AND model = ?", (utt_id, model)
        ).fetchone()
        if row is not None:
            if row[0] != text:
                raise ValueError(f"{model!r} already has a different transcript of {utt_id!r}")
            return
        with self._db:
            self._db.execute(
                "INSERT INTO hypotheses (utt_id, model, text) VALUES (?, ?, ?)",
                (utt_id, model, text),
            )

    def get(self, utt_id: str) -> Utterance:
        """Return an utterance and every hypothesis recorded for it. Unknown ids raise KeyError."""
        utt_id = nfc(utt_id)
        reference = self._reference(utt_id)
        if reference is None:
            raise KeyError(utt_id)
        rows = self._db.execute("SELECT model, text FROM hypotheses WHERE utt_id = ?", (utt_id,))
        return Utterance(utt_id, reference, dict(rows))

    def pairs(self, model: str) -> list[tuple[str, str, str]]:
        """(utt_id, reference, hypothesis) for every utterance the model transcribed,
        in the order the utterances were added."""
        rows = self._db.execute(
            "SELECT u.utt_id, u.reference, h.text FROM utterances u"
            " JOIN hypotheses h ON h.utt_id = u.utt_id WHERE h.model = ? ORDER BY u.seq",
            (nfc(model),),
        )
        return [tuple(row) for row in rows]

    def close(self) -> None:
        self._db.close()

    def _reference(self, utt_id: str) -> str | None:
        row = self._db.execute(
            "SELECT reference FROM utterances WHERE utt_id = ?", (utt_id,)
        ).fetchone()
        return None if row is None else row[0]
