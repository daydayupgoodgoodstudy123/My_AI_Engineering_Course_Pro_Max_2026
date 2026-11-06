"""Who holds the floor in a voice loop, and what happens when the user cuts in."""
from __future__ import annotations


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

    def user_turn(self, t_ns: int, text: str) -> int:
        """The user finished an utterance: start the next reply and return its number (1, 2, ...)."""
        raise NotImplementedError

    def audio(self, t_ns: int, reply: int, text: str, duration_ns: int) -> None:
        """TTS produced the next chunk of reply."""
        raise NotImplementedError

    def reply_done(self, t_ns: int, reply: int) -> None:
        """The reply has no more chunks."""
        raise NotImplementedError

    def mic(self, t_ns: int, speech: bool) -> None:
        """One VAD decision, for the mic frame captured at t_ns."""
        raise NotImplementedError
