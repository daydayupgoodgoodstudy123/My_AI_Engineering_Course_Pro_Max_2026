"""Who holds the floor in a voice loop, and what happens when the user cuts in."""
from __future__ import annotations

from collections import deque


class Dialog:
    """Turn-taking for a voice agent: listening -> thinking -> speaking -> listening.

    Times are integer nanoseconds on the mic clock, and calls arrive in time order.

    - user_turn(t, text): the user finished an utterance, and the next reply starts: thinking.
    - audio(t, reply, text, duration_ns): TTS made the next chunk of a reply. A reply's chunks
      play back to back in the order they arrive: a chunk starts when it arrives or when the
      chunk before it ends, whichever is later. Once the first chunk starts: speaking.
    - reply_done(t, reply): the reply has no more chunks. When its last chunk has played,
      the dialog is listening again.
    - mic(t, speech): the VAD decision for the 20 ms mic frame captured at t, after echo
      cancellation.

    Barge-in: while thinking or speaking, barge_in_frames speech frames in a row cancel the
    reply at the time of the last of them. Playback stops right there, even in the middle of
    a chunk. Queued chunks are dropped, and chunks that arrive later for a cancelled reply are
    ignored. A user_turn while a reply still holds the floor cancels it the same way.

    played lists what reached the speaker as (start_ns, end_ns, text); a chunk cut short ends
    at the cut. history lists the conversation as (role, text): every user turn, and for every
    reply the text the user heard, that is its chunks that started playing, joined by spaces.
    A reply that never made a sound leaves no entry.
    """

    def __init__(self, barge_in_frames: int = 3) -> None:
        self.barge_in_frames = barge_in_frames
        self.state = "listening"
        self.played: list[tuple[int, int, str]] = []
        self.history: list[tuple[str, str]] = []
        self._replies = 0
        self._active: int | None = None  # number of the reply that holds the floor
        self._queue: deque[tuple[int, int, str]] = deque()  # scheduled, not started yet
        self._heard: list[str] = []
        self._end = 0  # when the last scheduled chunk of the active reply ends
        self._done = False
        self._speech = 0  # speech frames in a row

    def user_turn(self, t_ns: int, text: str) -> int:
        """The user finished an utterance: start the next reply and return its number (1, 2, ...)."""
        self._advance(t_ns)
        if self._active is not None:
            self._cut(t_ns)
        self.history.append(("user", text))
        self._replies += 1
        self._active = self._replies
        self._end = t_ns
        self.state = "thinking"
        return self._active

    def audio(self, t_ns: int, reply: int, text: str, duration_ns: int) -> None:
        """TTS produced the next chunk of reply."""
        self._advance(t_ns)
        if reply != self._active or self._done:
            return
        start = max(t_ns, self._end)
        self._end = start + duration_ns
        self._queue.append((start, self._end, text))
        self._advance(t_ns)

    def reply_done(self, t_ns: int, reply: int) -> None:
        """The reply has no more chunks."""
        self._advance(t_ns)
        if reply == self._active:
            self._done = True
            self._advance(t_ns)

    def mic(self, t_ns: int, speech: bool) -> None:
        """One VAD decision, for the mic frame captured at t_ns."""
        self._advance(t_ns)
        self._speech = self._speech + 1 if speech else 0
        if self._active is not None and self._speech >= self.barge_in_frames:
            self._cut(t_ns)

    def _advance(self, t_ns: int) -> None:
        """Bring playback up to t_ns."""
        while self._queue and self._queue[0][0] <= t_ns:
            chunk = self._queue.popleft()
            self.played.append(chunk)
            self._heard.append(chunk[2])
            self.state = "speaking"
        if self._active is not None and self._done and not self._queue and self._end <= t_ns:
            self._finish()

    def _cut(self, t_ns: int) -> None:
        """Barge-in: stop the active reply at t_ns."""
        if self._heard and self.played[-1][1] > t_ns:
            start, _, text = self.played[-1]
            self.played[-1] = (start, t_ns, text)
        self._finish()

    def _finish(self) -> None:
        if self._heard:
            self.history.append(("assistant", " ".join(self._heard)))
        self._active = None
        self._queue.clear()
        self._heard = []
        self._done = False
        self.state = "listening"
