"""Original interview practice for 04-computer-vision/23-diffusion-transformers-rectified-flow.

Local source: phases/04-computer-vision/23-diffusion-transformers-rectified-flow/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def flow_step(state, velocity, delta):
    if len(state) != len(velocity) or not 0 <= delta <= 1:
        raise ValueError('contract')
    return [x + delta * v for x, v in zip(state, velocity)]

def diffuse(clean, noise, alpha_bar):
    if len(clean) != len(noise) or not 0 <= alpha_bar <= 1:
        raise ValueError('contract')
    return [math.sqrt(alpha_bar) * x + math.sqrt(1 - alpha_bar) * z for x, z in zip(clean, noise)]
