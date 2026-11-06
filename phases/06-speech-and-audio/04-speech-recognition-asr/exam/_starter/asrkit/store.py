"""Reference transcripts and model hypotheses, stored in SQLite."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Utterance:
    utt_id: str
    reference: str
    hypotheses: dict[str, str]  # model version -> what it transcribed


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
        # TODO: create the schema

    def add_utterance(self, utt_id: str, reference: str) -> None:
        """Register an utterance with its reference transcript. A known id raises ValueError."""
        raise NotImplementedError

    def add_hypothesis(self, utt_id: str, model: str, text: str) -> None:
        """Record what one model version transcribed for an utterance.

        Unknown utterances raise KeyError. A model version never changes its mind:
        recording the same transcript again does nothing, a different one raises ValueError.
        """
        raise NotImplementedError

    def get(self, utt_id: str) -> Utterance:
        """Return an utterance and every hypothesis recorded for it. Unknown ids raise KeyError."""
        raise NotImplementedError

    def pairs(self, model: str) -> list[tuple[str, str, str]]:
        """(utt_id, reference, hypothesis) for every utterance the model transcribed,
        in the order the utterances were added."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
