"""Original interview practice for 06-speech-and-audio/15-streaming-speech-to-speech-moshi-hibiki.

Local source: phases/06-speech-and-audio/15-streaming-speech-to-speech-moshi-hibiki/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def quantize_codebook(vectors, codebook):
    if not codebook or any((len(c) != len(codebook[0]) for c in codebook)) or any((len(v) != len(codebook[0]) for v in vectors)):
        raise ValueError('codebook')
    return [min(range(len(codebook)), key=lambda i: sum(((a - b) ** 2 for a, b in zip(v, codebook[i])))) for v in vectors]

def latency_report(latencies, deadline):
    if not latencies or any((t < 0 for t in latencies)) or deadline < 0:
        raise ValueError('latency')
    ordered = sorted(latencies)
    n = len(ordered)
    return {'p50': ordered[math.ceil(0.5 * n) - 1], 'p95': ordered[math.ceil(0.95 * n) - 1], 'goodput_fraction': sum((t <= deadline for t in latencies)) / n}
