"""CTC decoding over the per-frame output of an acoustic model.

Token 0 is the CTC blank, 1-26 are the letters a-z and 27 is the space between words,
as in the lesson. A frame is a list of log-probabilities over those tokens, the way a
log_softmax returns them; a token the model rules out entirely has -inf.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

VOCAB = "_abcdefghijklmnopqrstuvwxyz "
BLANK = 0
SPACE = VOCAB.index(" ")

Frame = list[float]
Prefix = tuple[int, ...]


def argmax(frame: Frame) -> int:
    """Index of the most likely token; the lowest index wins a tie."""
    return max(range(len(frame)), key=frame.__getitem__)


def greedy_decode(frames: Sequence[Frame], blank: int = BLANK) -> list[int]:
    """Best-path decoding: take the most likely token of every frame, merge consecutive
    repeats, then drop blanks. A blank between two equal tokens keeps both of them.
    """
    out: list[int] = []
    prev = None
    for token in map(argmax, frames):
        if token != blank and token != prev:
            out.append(token)
        prev = token
    return out


def to_text(tokens: Sequence[int]) -> str:
    """Spell token ids out as words separated by single spaces."""
    return " ".join("".join(VOCAB[t] for t in tokens).split())


def transcribe(frames: Sequence[Frame], beam: int | None = None) -> str:
    """Transcript of one utterance: greedy decoding, or prefix beam search if beam is given."""
    if beam is None:
        return to_text(greedy_decode(frames))
    return to_text(prefix_beam_search(frames, beam)[0][0])


def log_add(a: float, b: float) -> float:
    """log(exp(a) + exp(b)) for two log-probabilities, without underflow. Either may be -inf."""
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    return max(a, b) + math.log1p(math.exp(-abs(a - b)))


def prefix_beam_search(
    frames: Sequence[Frame], beam: int = 8, blank: int = BLANK
) -> list[tuple[Prefix, float]]:
    """CTC prefix beam search.

    The probability of a prefix is the total over every alignment that collapses to it
    (merge repeats, then drop blanks), so it can beat the single best path. After each
    frame only the `beam` most probable prefixes are kept. Everything stays in the log
    domain, so long utterances do not underflow.

    Returns up to `beam` (prefix, log probability) pairs, most probable first; equal
    scores put the smaller prefix first. Prefixes with zero probability are left out.
    """
    if beam < 1:
        raise ValueError(f"beam must be at least 1, got {beam}")
    neg = -math.inf
    # prefix -> (log P of alignments ending in a blank, log P of those ending in its last token)
    beams: dict[Prefix, tuple[float, float]] = {(): (0.0, neg)}
    for frame in frames:
        nxt: dict[Prefix, tuple[float, float]] = {}

        def add(prefix: Prefix, ends_blank: float = neg, ends_token: float = neg) -> None:
            b, t = nxt.get(prefix, (neg, neg))
            nxt[prefix] = (log_add(b, ends_blank), log_add(t, ends_token))

        for prefix, (p_blank, p_token) in beams.items():
            total = log_add(p_blank, p_token)
            add(prefix, ends_blank=total + frame[blank])
            for token, lp in enumerate(frame):
                if token == blank or lp == neg:
                    continue
                if prefix and prefix[-1] == token:
                    add(prefix, ends_token=p_token + lp)  # the same token held: no new letter
                    add(prefix + (token,), ends_token=p_blank + lp)  # a blank came between
                else:
                    add(prefix + (token,), ends_token=total + lp)
        ranked = sorted(
            ((prefix, log_add(*mass)) for prefix, mass in nxt.items()),
            key=lambda item: (-item[1], item[0]),
        )
        beams = {prefix: nxt[prefix] for prefix, score in ranked[:beam] if score > neg}
    result = [(prefix, log_add(*mass)) for prefix, mass in beams.items()]
    return sorted(result, key=lambda item: (-item[1], item[0]))
