"""Original interview practice for 08-generative-ai/09-inpainting-outpainting-editing.

Local source: phases/08-generative-ai/09-inpainting-outpainting-editing/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def rle_encode(values):
    if any((type(x) is not bool for x in values)):
        raise ValueError('mask')
    runs = []
    for x in values:
        if runs and runs[-1][0] == x:
            runs[-1][1] += 1
        else:
            runs.append([x, 1])
    return runs

def diffuse(clean, noise, alpha_bar):
    if len(clean) != len(noise) or not 0 <= alpha_bar <= 1:
        raise ValueError('contract')
    return [math.sqrt(alpha_bar) * x + math.sqrt(1 - alpha_bar) * z for x, z in zip(clean, noise)]
