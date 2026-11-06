"""Glue used by the API layer: live sessions, the session log and the training-data path."""
from __future__ import annotations

from .log import SessionLog
from .mimi import encode, frames_of
from .model import DuplexSession, ToyMoshi
from .monologue import Word, align, transcript


class DuplexService:
    def __init__(self, log: SessionLog, model_factory=ToyMoshi) -> None:
        self.log = log
        self.model_factory = model_factory

    def open(self) -> DuplexSession:
        """A new live session with a fresh model."""
        return DuplexSession(self.model_factory())

    def record(
        self, session: str, user_pcm: list[float], model_pcm: list[float], words: list[Word]
    ) -> int:
        """Log a recorded two-sided dialogue as training data and return its length in frames.

        Both sides are Mimi-encoded; the model side's timed words become its inner monologue.
        """
        user = frames_of(encode(user_pcm))
        model = frames_of(encode(model_pcm))
        if len(user) != len(model):
            raise ValueError(f"the two sides have {len(user)} and {len(model)} frames")
        text = align(words, len(model))
        for index, (heard, spoken, token) in enumerate(zip(user, model, text)):
            self.log.add_user(session, index, heard)
            self.log.add_model(session, index, token, spoken)
        return len(model)

    def transcript(self, session: str) -> list[tuple[int, list[int]]]:
        """The model's words in a logged session, read off its inner monologue."""
        return transcript([frame.text for frame in self.log.frames(session)])
