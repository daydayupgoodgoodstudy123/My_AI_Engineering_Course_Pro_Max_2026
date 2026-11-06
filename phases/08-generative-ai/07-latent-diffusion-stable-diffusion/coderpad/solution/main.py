"""Original interview practice for 08-generative-ai/07-latent-diffusion-stable-diffusion.

Local source: phases/08-generative-ai/07-latent-diffusion-stable-diffusion/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def diffuse(clean, noise, alpha_bar):
    if len(clean) != len(noise) or not 0 <= alpha_bar <= 1:
        raise ValueError('contract')
    return [math.sqrt(alpha_bar) * x + math.sqrt(1 - alpha_bar) * z for x, z in zip(clean, noise)]

def quantize(values, bits):
    if type(bits) is not int or not 2 <= bits <= 8:
        raise ValueError('bits')
    bound = 2 ** (bits - 1) - 1
    maximum = max((abs(x) for x in values), default=0)
    scale = maximum / bound if maximum else 1
    return {'values': [max(-bound, min(bound, round(x / scale))) for x in values], 'scale': scale}
