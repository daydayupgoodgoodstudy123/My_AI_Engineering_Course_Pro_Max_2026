"""Original interview practice for 12-multimodal-ai/14-show-o-discrete-diffusion-unified.

Local source: phases/12-multimodal-ai/14-show-o-discrete-diffusion-unified/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def masked_probabilities(logits, allowed):
    if not logits or not allowed or any((type(i) is not int or not 0 <= i < len(logits) for i in allowed)) or (len(set(allowed)) != len(allowed)):
        raise ValueError('mask')
    maximum = max((logits[i] for i in allowed))
    weights = {i: math.exp(logits[i] - maximum) for i in allowed}
    total = sum(weights.values())
    return [weights.get(i, 0) / total for i in range(len(logits))]

def diffuse(clean, noise, alpha_bar):
    if len(clean) != len(noise) or not 0 <= alpha_bar <= 1:
        raise ValueError('contract')
    return [math.sqrt(alpha_bar) * x + math.sqrt(1 - alpha_bar) * z for x, z in zip(clean, noise)]
