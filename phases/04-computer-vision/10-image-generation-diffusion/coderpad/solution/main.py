"""Original interview practice for 04-computer-vision/10-image-generation-diffusion.

Local source: phases/04-computer-vision/10-image-generation-diffusion/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def diffuse(clean, noise, alpha_bar):
    if len(clean) != len(noise) or not 0 <= alpha_bar <= 1:
        raise ValueError('contract')
    return [math.sqrt(alpha_bar) * x + math.sqrt(1 - alpha_bar) * z for x, z in zip(clean, noise)]

def learning_rate(step, total, warmup, peak):
    if any((type(x) is not int for x in (step, total, warmup))) or total <= 0 or (not 0 <= warmup < total) or (step < 0) or (peak < 0):
        raise ValueError('schedule')
    if step < warmup:
        return peak * step / warmup
    return peak * (1 + math.cos(math.pi * min(1, (step - warmup) / (total - warmup)))) / 2
