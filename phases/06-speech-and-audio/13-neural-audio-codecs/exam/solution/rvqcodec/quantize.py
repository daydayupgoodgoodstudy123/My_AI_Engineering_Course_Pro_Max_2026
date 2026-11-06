"""Residual vector quantization (RVQ), the bottleneck of a neural audio codec.

A frame is one encoder output vector, a list of floats. A codebook is a list of codewords,
each as long as a frame. Codes are laid out like a codec's (n_q, n_frames) code tensor:
codes[q][t] is the index that stage q picked for frame t.
"""
from __future__ import annotations


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def energies(codebook: list[list[float]]) -> list[float]:
    """Squared length of every codeword."""
    return [dot(c, c) for c in codebook]


def assign(frames: list[list[float]], codebook: list[list[float]]) -> list[int]:
    """Index of the nearest codeword, by squared Euclidean distance, for every frame.

    ||f - c||^2 = ||f||^2 - 2 f.c + ||c||^2, and ||f||^2 is the same for every codeword,
    so codewords are ranked by ||c||^2 - 2 f.c. Ties go to the lower index.
    """
    energy = energies(codebook)
    scores = [
        [e - 2.0 * dot(frame, codeword) for e, codeword in zip(energy, codebook)]
        for frame in frames
    ]
    return [min(range(len(row)), key=row.__getitem__) for row in scores]


def rvq_encode(frames: list[list[float]], codebooks: list[list[list[float]]]) -> list[list[int]]:
    """Quantize frames stage by stage and return codes[q][t].

    Stage 0 quantizes the frames, and every later stage quantizes the residual that the
    stages before it left. The frames themselves are not modified.
    """
    residual = [list(frame) for frame in frames]
    codes = []
    for codebook in codebooks:
        indices = assign(residual, codebook)
        codes.append(indices)
        residual = [[r - c for r, c in zip(res, codebook[i])] for res, i in zip(residual, indices)]
    return codes


def rvq_decode(codes: list[list[int]], codebooks: list[list[list[float]]]) -> list[list[float]]:
    """Rebuild frames by adding up one codeword per stage.

    Decoding only the first q rows of codes with the first q codebooks gives the
    lower-bitrate reconstruction from those stages alone.
    """
    if not codes:
        return []
    dim = len(codebooks[0][0])
    out = [[0.0] * dim for _ in codes[0]]
    for row, codebook in zip(codes, codebooks):
        for t, i in enumerate(row):
            for j, v in enumerate(codebook[i]):
                out[t][j] += v
    return out


def mse(a: list[list[float]], b: list[list[float]]) -> float:
    """Mean squared error between two lists of frames, per value."""
    n = sum(len(frame) for frame in a)
    return sum((x - y) ** 2 for fa, fb in zip(a, b) for x, y in zip(fa, fb)) / n
