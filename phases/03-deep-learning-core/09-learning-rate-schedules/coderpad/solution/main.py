"""Original interview practice for 03-deep-learning-core/09-learning-rate-schedules.

Local source: phases/03-deep-learning-core/09-learning-rate-schedules/docs/en.md (sha256 in SCOPE.json).
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

def gradient_step(weights, gradients, rate):
    if len(weights) != len(gradients) or rate < 0:
        raise ValueError('contract')
    return [w - rate * g for w, g in zip(weights, gradients)]
