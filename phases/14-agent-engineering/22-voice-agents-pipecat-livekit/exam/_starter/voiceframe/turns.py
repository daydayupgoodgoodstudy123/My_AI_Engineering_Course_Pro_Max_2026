"""Turn taking: when the user is done, what reaches the LLM, and when the bot must stop."""
from __future__ import annotations

from .frames import UPSTREAM, Frame

REPEAT_PROMPT = "could you repeat that?"


class TurnTaker:
    """Sits between STT and the LLM, and guards what reaches the transport.

    All times are milliseconds on the call clock.

    The user's side. STT hands over final transcript segments, the VAD reports
    when the user starts and stops speaking, and tick() lets time pass. The
    segments of one turn are stripped and joined with single spaces; a segment
    that is empty after stripping is ignored, confidence included. A turn ends:

    - at once, when a segment leaves the joined text ending with "?";
    - otherwise, at a tick once the user has been silent for at least silence_ms
      since they last stopped speaking, if the turn has any text.

    Every ended turn takes the next turn number; the first is 1. If every segment
    of the turn has a confidence of at least threshold, the turn goes on as
    Frame("transcript", text, turn=n). Otherwise the LLM never sees it and
    Frame("text", REPEAT_PROMPT, turn=n) goes straight to TTS.

    The bot's side. bot_started(turn) and bot_stopped(turn) say when the bot is
    speaking the reply to a turn. When the user starts speaking while the bot is
    speaking, user_started returns Frame("cancel", None, UPSTREAM, turn=<that turn>),
    once per bot turn. admit(frame) says whether a frame from the LLM or TTS may go
    on to the transport: only frames of the latest turn, even before the bot starts
    speaking it, and none of a turn that was cancelled.
    """

    def __init__(self, threshold: float = 0.6, silence_ms: int = 700) -> None:
        self.threshold = threshold
        self.silence_ms = silence_ms

    def user_started(self, t_ms: int) -> list[Frame]:
        raise NotImplementedError

    def user_stopped(self, t_ms: int) -> list[Frame]:
        raise NotImplementedError

    def transcript(self, t_ms: int, text: str, confidence: float) -> list[Frame]:
        raise NotImplementedError

    def tick(self, t_ms: int) -> list[Frame]:
        raise NotImplementedError

    def bot_started(self, turn: int) -> None:
        raise NotImplementedError

    def bot_stopped(self, turn: int) -> None:
        raise NotImplementedError

    def admit(self, frame: Frame) -> bool:
        raise NotImplementedError
