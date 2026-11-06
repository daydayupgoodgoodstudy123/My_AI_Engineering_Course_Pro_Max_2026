"""Original interview practice for 08-generative-ai/11-audio-generation.

Local source: phases/08-generative-ai/11-audio-generation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def audio_frames(samples, width, hop):
    if any((type(x) is not int or x <= 0 for x in (width, hop))):
        raise ValueError('window')
    return [samples[i:i + width] for i in range(0, len(samples) - width + 1, hop)]

def quantize_codebook(vectors, codebook):
    if not codebook or any((len(c) != len(codebook[0]) for c in codebook)) or any((len(v) != len(codebook[0]) for v in vectors)):
        raise ValueError('codebook')
    return [min(range(len(codebook)), key=lambda i: sum(((a - b) ** 2 for a, b in zip(v, codebook[i])))) for v in vectors]
