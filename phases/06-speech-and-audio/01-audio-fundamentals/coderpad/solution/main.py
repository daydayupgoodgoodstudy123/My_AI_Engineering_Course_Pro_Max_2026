"""Original interview practice for 06-speech-and-audio/01-audio-fundamentals.

Local source: phases/06-speech-and-audio/01-audio-fundamentals/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dft(samples):
    n = len(samples)
    return [[sum((x * math.cos(-2 * math.pi * k * j / n) for j, x in enumerate(samples))), sum((x * math.sin(-2 * math.pi * k * j / n) for j, x in enumerate(samples)))] for k in range(n)]

def energy_vad(chunks, threshold):
    if threshold < 0:
        raise ValueError('threshold')
    return [math.sqrt(sum((x * x for x in c)) / len(c)) >= threshold if c else 0 >= threshold for c in chunks]
