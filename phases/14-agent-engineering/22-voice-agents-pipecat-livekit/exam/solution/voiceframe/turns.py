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
        self.turn = 0
        self._parts: list[str] = []
        self._confidences: list[float] = []
        self._user_speaking = False
        self._stopped_at: int | None = None
        self._bot_turn: int | None = None
        self._cancelled: set[int] = set()

    def user_started(self, t_ms: int) -> list[Frame]:
        self._user_speaking = True
        bot = self._bot_turn
        if bot is not None and bot not in self._cancelled:
            self._cancelled.add(bot)
            return [Frame("cancel", None, UPSTREAM, turn=bot)]
        return []

    def user_stopped(self, t_ms: int) -> list[Frame]:
        self._user_speaking = False
        self._stopped_at = t_ms
        return []

    def transcript(self, t_ms: int, text: str, confidence: float) -> list[Frame]:
        text = text.strip()
        if not text:
            return []
        self._parts.append(text)
        self._confidences.append(confidence)
        if text.endswith("?"):
            return self._end_turn()
        return []

    def tick(self, t_ms: int) -> list[Frame]:
        if (
            self._parts
            and not self._user_speaking
            and self._stopped_at is not None
            and t_ms - self._stopped_at >= self.silence_ms
        ):
            return self._end_turn()
        return []

    def bot_started(self, turn: int) -> None:
        self._bot_turn = turn

    def bot_stopped(self, turn: int) -> None:
        if self._bot_turn == turn:
            self._bot_turn = None

    def admit(self, frame: Frame) -> bool:
        return frame.turn == self.turn and frame.turn not in self._cancelled

    def _end_turn(self) -> list[Frame]:
        self.turn += 1
        text = " ".join(self._parts)
        confident = min(self._confidences) >= self.threshold
        self._parts = []
        self._confidences = []
        if confident:
            return [Frame("transcript", text, turn=self.turn)]
        return [Frame("text", REPEAT_PROMPT, turn=self.turn)]
