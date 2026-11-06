"""Original interview practice for 06-speech-and-audio/11-real-time-audio-processing.

Local source: phases/06-speech-and-audio/11-real-time-audio-processing/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def energy_vad(chunks, threshold):
    if threshold < 0:
        raise ValueError('threshold')
    return [math.sqrt(sum((x * x for x in c)) / len(c)) >= threshold if c else 0 >= threshold for c in chunks]

def latency_report(latencies, deadline):
    if not latencies or any((t < 0 for t in latencies)) or deadline < 0:
        raise ValueError('latency')
    ordered = sorted(latencies)
    n = len(ordered)
    return {'p50': ordered[math.ceil(0.5 * n) - 1], 'p95': ordered[math.ceil(0.95 * n) - 1], 'goodput_fraction': sum((t <= deadline for t in latencies)) / n}
