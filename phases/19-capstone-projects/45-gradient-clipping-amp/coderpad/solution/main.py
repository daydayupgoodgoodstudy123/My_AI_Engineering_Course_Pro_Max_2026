"""Original interview practice for 19-capstone-projects/45-gradient-clipping-amp.

Local source: phases/19-capstone-projects/45-gradient-clipping-amp/docs/en.md (sha256 in SCOPE.json).
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

def gradient_step(weights, gradients, rate):
    if len(weights) != len(gradients) or rate < 0:
        raise ValueError('contract')
    return [w - rate * g for w, g in zip(weights, gradients)]
