"""Original interview practice for 19-capstone-projects/44-cosine-lr-warmup.

Local source: phases/19-capstone-projects/44-cosine-lr-warmup/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def learning_rate(step, total, warmup, peak):
    if any((type(x) is not int for x in (step, total, warmup))) or total <= 0 or (not 0 <= warmup < total) or (step < 0) or (peak < 0):
        raise ValueError('schedule')
    if step < warmup:
        return peak * step / warmup
    return peak * (1 + math.cos(math.pi * min(1, (step - warmup) / (total - warmup)))) / 2

def clip_gradients(gradients, maximum):
    if maximum < 0:
        raise ValueError('maximum')
    norm = math.sqrt(sum((g * g for g in gradients)))
    scale = min(1, maximum / norm) if norm else 1
    return [g * scale for g in gradients]
