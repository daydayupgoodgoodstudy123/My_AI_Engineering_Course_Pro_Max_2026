"""Original interview practice for 06-speech-and-audio/13-neural-audio-codecs.

Local source: phases/06-speech-and-audio/13-neural-audio-codecs/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def quantize_codebook(vectors, codebook):
    if not codebook or any((len(c) != len(codebook[0]) for c in codebook)) or any((len(v) != len(codebook[0]) for v in vectors)):
        raise ValueError('codebook')
    return [min(range(len(codebook)), key=lambda i: sum(((a - b) ** 2 for a, b in zip(v, codebook[i])))) for v in vectors]

def mse(predicted, expected):
    if not predicted or len(predicted) != len(expected):
        raise ValueError('shape')
    return sum(((a - b) ** 2 for a, b in zip(predicted, expected))) / len(predicted)
