"""Original interview practice for 03-deep-learning-core/13-debugging-neural-networks.

Local source: phases/03-deep-learning-core/13-debugging-neural-networks/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def clip_gradients(gradients, maximum):
    if maximum < 0:
        raise ValueError('maximum')
    norm = math.sqrt(sum((g * g for g in gradients)))
    scale = min(1, maximum / norm) if norm else 1
    return [g * scale for g in gradients]

def zscore_flags(values, threshold):
    if threshold < 0:
        raise ValueError('threshold')
    if not values:
        return []
    mean = sum(values) / len(values)
    sd = math.sqrt(sum(((x - mean) ** 2 for x in values)) / len(values))
    return [abs(x - mean) / sd > threshold if sd else False for x in values]
