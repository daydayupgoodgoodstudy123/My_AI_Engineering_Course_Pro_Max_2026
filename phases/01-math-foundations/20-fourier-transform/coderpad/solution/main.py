"""Original interview practice for 01-math-foundations/20-fourier-transform.

Local source: phases/01-math-foundations/20-fourier-transform/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dft(samples):
    n = len(samples)
    return [[sum((x * math.cos(-2 * math.pi * k * j / n) for j, x in enumerate(samples))), sum((x * math.sin(-2 * math.pi * k * j / n) for j, x in enumerate(samples)))] for k in range(n)]

def audio_frames(samples, width, hop):
    if any((type(x) is not int or x <= 0 for x in (width, hop))):
        raise ValueError('window')
    return [samples[i:i + width] for i in range(0, len(samples) - width + 1, hop)]
