"""Decoder inputs for an audio-language model: audio slots, merged vectors, padded batches.

This is the lesson's three-component template seen from the input side. The encoder turns
16 kHz audio into one frame every 20 ms (50 frames per second). The projector stacks `stack`
consecutive frames into one vector and maps it into the LLM's embedding space; each projected
vector is one audio token. A prompt marks each clip with one AUDIO slot. expand() widens the
slot to AUDIO_BOS, one AUDIO_PAD per audio token and AUDIO_EOS, and merge() puts the projected
vectors at the AUDIO_PAD positions.
"""
from __future__ import annotations

SAMPLE_RATE = 16000
FRAME_SAMPLES = 320  # 20 ms at 16 kHz
STACK = 2

EOS = 2
PAD = EOS  # Qwen-style tokenizers pad with the end-of-text token
AUDIO = 7
AUDIO_BOS = 8
AUDIO_PAD = 9
AUDIO_EOS = 10


def encoder_frames(num_samples: int) -> int:
    """Encoder frames for num_samples of 16 kHz audio. A trailing partial frame is padded, so it counts."""
    return -(-num_samples // FRAME_SAMPLES)


def audio_tokens(num_frames: int, stack: int = STACK) -> int:
    """Audio tokens the projector makes from num_frames encoder frames (see stack_frames)."""
    return num_frames // stack


def clip_tokens(num_samples: int, stack: int = STACK) -> int:
    """Audio tokens for a clip of num_samples 16 kHz samples."""
    return audio_tokens(encoder_frames(num_samples), stack)


def stack_frames(frames: list[list[float]], stack: int = STACK) -> list[list[float]]:
    """Concatenate each run of `stack` consecutive frames into one vector.

    A trailing partial run is zero-padded, so no frame is dropped.
    """
    if not frames:
        return []
    width = len(frames[0]) * stack
    out = []
    for start in range(0, len(frames), stack):
        flat = [v for frame in frames[start : start + stack] for v in frame]
        out.append(flat + [0.0] * (width - len(flat)))
    return out


def project(
    frames: list[list[float]], weights: list[list[float]], stack: int = STACK
) -> list[list[float]]:
    """The projector: stack the frames, then map each stacked vector through weights (one row per output)."""
    return [[sum(w * x for w, x in zip(row, vec)) for row in weights] for vec in stack_frames(frames, stack)]


def expand(prompt: list[int], counts: list[int]) -> list[int]:
    """Widen the i-th AUDIO slot, where it stands, to AUDIO_BOS, counts[i] AUDIO_PAD tokens and AUDIO_EOS."""
    if prompt.count(AUDIO) != len(counts):
        raise ValueError(f"{prompt.count(AUDIO)} audio slots for {len(counts)} clips")
    audio = [token for n in counts for token in [AUDIO_BOS] + [AUDIO_PAD] * n + [AUDIO_EOS]]
    return audio + [token for token in prompt if token != AUDIO]


def merge(ids: list[int], embed: dict[int, list[float]], audio: list[list[float]]) -> list[list[float]]:
    """Decoder input vectors: embed[t] for every other token, the audio vectors in order at the AUDIO_PAD positions."""
    slots = ids.count(AUDIO_PAD)
    if slots != len(audio):
        raise ValueError(f"{len(audio)} audio vectors for {slots} AUDIO_PAD positions")
    vectors = iter(audio)
    return [next(vectors) if token == AUDIO_PAD else embed[token] for token in ids]


def assemble(
    prompt: list[int],
    clips: list[list[list[float]]],
    embed: dict[int, list[float]],
    weights: list[list[float]],
    stack: int = STACK,
) -> tuple[list[int], list[list[float]]]:
    """Ids and decoder input vectors for one prompt. clips holds each clip's encoder frames, in slot order."""
    ids = expand(prompt, [audio_tokens(len(frames), stack) for frames in clips])
    audio = [vec for frames in clips for vec in project(frames, weights, stack)]
    return ids, merge(ids, embed, audio)


def pad_batch(rows: list[list[int]]) -> tuple[list[list[int]], list[list[int]], list[list[int]]]:
    """Left-pad rows to one width for generation. Returns (ids, attention_mask, position_ids).

    The mask is 1 on a row's own tokens and 0 on its padding. Positions count a row's own
    tokens from 0; padding sits at position 0.
    """
    width = max(len(row) for row in rows)
    ids = [[PAD] * (width - len(row)) + row for row in rows]
    mask = [[int(token != PAD) for token in row] for row in ids]
    positions = [[max(0, sum(m[: j + 1]) - 1) for j in range(width)] for m in mask]
    return ids, mask, positions
