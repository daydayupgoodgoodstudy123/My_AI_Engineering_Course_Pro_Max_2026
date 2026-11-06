"""Original interview practice for 12-multimodal-ai/12-emu3-next-token-for-generation.

Local source: phases/12-multimodal-ai/12-emu3-next-token-for-generation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def causal_mask(length, window=None):
    if type(length) is not int or length < 0 or (window is not None and (type(window) is not int or window <= 0)):
        raise ValueError('shape')
    return [[j <= i and (window is None or i - j < window) for j in range(length)] for i in range(length)]

def quantize_codebook(vectors, codebook):
    if not codebook or any((len(c) != len(codebook[0]) for c in codebook)) or any((len(v) != len(codebook[0]) for v in vectors)):
        raise ValueError('codebook')
    return [min(range(len(codebook)), key=lambda i: sum(((a - b) ** 2 for a, b in zip(v, codebook[i])))) for v in vectors]
