"""Original interview practice for 06-speech-and-audio/03-audio-classification.

Local source: phases/06-speech-and-audio/03-audio-classification/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def energy_vad(chunks, threshold):
    if threshold < 0:
        raise ValueError('threshold')
    return [math.sqrt(sum((x * x for x in c)) / len(c)) >= threshold if c else 0 >= threshold for c in chunks]

def nearest(query, points, k):
    if type(k) is not int or not 0 <= k <= len(points) or any((len(p) != len(query) for p in points)):
        raise ValueError('contract')
    return sorted(range(len(points)), key=lambda i: (sum(((a - b) ** 2 for a, b in zip(query, points[i]))), i))[:k]
