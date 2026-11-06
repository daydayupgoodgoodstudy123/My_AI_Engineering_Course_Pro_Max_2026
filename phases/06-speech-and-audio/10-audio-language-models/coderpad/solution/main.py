"""Original interview practice for 06-speech-and-audio/10-audio-language-models.

Local source: phases/06-speech-and-audio/10-audio-language-models/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def audio_frames(samples, width, hop):
    if any((type(x) is not int or x <= 0 for x in (width, hop))):
        raise ValueError('window')
    return [samples[i:i + width] for i in range(0, len(samples) - width + 1, hop)]

def attention(query, keys, values):
    if not query or not keys or len(keys) != len(values) or any((len(k) != len(query) for k in keys)) or (not values[0]) or any((len(v) != len(values[0]) for v in values)):
        raise ValueError('shape')
    scores = [sum((a * b for a, b in zip(query, k))) / math.sqrt(len(query)) for k in keys]
    maximum = max(scores)
    weights = [math.exp(s - maximum) for s in scores]
    total = sum(weights)
    return [sum((w * v[j] for w, v in zip(weights, values))) / total for j in range(len(values[0]))]
