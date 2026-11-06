"""A toy Moshi, and the per-frame duplex loop that drives it."""
from __future__ import annotations

from dataclasses import dataclass

from .mimi import encode
from .tokens import CODEBOOK_SIZE, CODEBOOKS

_MOD = (1 << 61) - 1
TEXT_VOCAB = 4000


class ToyMoshi:
    """A deterministic stand-in for Moshi's two transformers.

    The temporal transformer's context is one integer that folds in a frame at a time, the way a
    KV cache grows by one step per frame. advance() folds in the user's frame t together with the
    model's own text token and audio frame from step t - 1 (TEXT_START and AUDIO_START codes
    before the first step). next_text() is the inner-monologue head. next_code() is the depth
    transformer: it predicts the next codebook of the model's current frame from the context,
    the frame's text token and the codebooks already predicted for this frame.
    """

    def initial(self) -> int:
        return 1

    def advance(self, state: int, user: list[int], text: int, audio: list[int]) -> int:
        for token in (*user, text, *audio):
            state = (state * 1_000_003 + token + 1) % _MOD
        return state

    def next_text(self, state: int) -> int:
        return 3 + state % (TEXT_VOCAB - 3)

    def next_code(self, state: int, text: int, prefix: list[int]) -> int:
        mixed = (state + 7_919 * text + 104_729 * len(prefix) + 31 * sum(prefix)) % _MOD
        return (mixed ^ (mixed >> 17)) % CODEBOOK_SIZE


@dataclass(frozen=True)
class Reply:
    """The model's frame t: its inner-monologue token and its codes, codebook 0 first."""

    frame: int
    text: int
    codes: list[int]


class DuplexStepper:
    """Runs a model one 80 ms frame at a time.

    Step t hears the user's frame t, then the model predicts its text token t (the inner
    monologue), then codebooks 0-7 of its own frame t one at a time, semantic first, each seeing
    the text token and the codebooks before it. So frame t is predicted from user frames 0..t
    and from the model's own text and audio up to t - 1. The context grows by one frame per step,
    so a step costs the same late in a long session as at its start.
    """

    def __init__(self, model) -> None:
        self.model = model
        self.user: list[list[int]] = []
        self.text: list[int] = []
        self.audio: list[list[int]] = []

    def step(self, user: list[int]) -> Reply:
        """Hear one user frame (its codes, codebook 0 first) and return the model's frame."""
        if len(user) != CODEBOOKS:
            raise ValueError(f"a user frame carries {CODEBOOKS} codes, got {len(user)}")
        state = self._context()
        text = self.model.next_text(state)
        codes: list[int] = []
        for _ in range(CODEBOOKS):
            codes.append(self.model.next_code(state, text, list(codes)))
        self.user.append(list(user))
        self.text.append(text)
        self.audio.append(codes)
        return Reply(len(self.text) - 1, text, codes)

    def _context(self):
        """The model's temporal context for the next prediction."""
        state = self.model.initial()
        for user, text, audio in zip(self.user, self.text, self.audio):
            state = self.model.advance(state, user, text, audio)
        return state


class DuplexSession:
    """A live session: user audio in, the model's frames out."""

    def __init__(self, model) -> None:
        self.stepper = DuplexStepper(model)

    def hear(self, pcm: list[float]) -> list[Reply]:
        """Run the model on the whole frames of a clip of user audio; one reply per frame."""
        return [self.stepper.step(codes) for codes in encode(pcm)]
