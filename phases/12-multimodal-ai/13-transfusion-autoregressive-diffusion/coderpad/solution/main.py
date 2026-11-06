"""Original interview practice for 12-multimodal-ai/13-transfusion-autoregressive-diffusion.

Local source: phases/12-multimodal-ai/13-transfusion-autoregressive-diffusion/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def diffuse(clean, noise, alpha_bar):
    if len(clean) != len(noise) or not 0 <= alpha_bar <= 1:
        raise ValueError('contract')
    return [math.sqrt(alpha_bar) * x + math.sqrt(1 - alpha_bar) * z for x, z in zip(clean, noise)]

def causal_mask(length, window=None):
    if type(length) is not int or length < 0 or (window is not None and (type(window) is not int or window <= 0)):
        raise ValueError('shape')
    return [[j <= i and (window is None or i - j < window) for j in range(length)] for i in range(length)]
