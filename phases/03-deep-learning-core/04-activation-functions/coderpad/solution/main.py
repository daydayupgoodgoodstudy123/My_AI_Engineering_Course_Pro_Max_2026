"""Original interview practice for 03-deep-learning-core/04-activation-functions.

Local source: phases/03-deep-learning-core/04-activation-functions/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def activation(values, kind='relu', slope=0.01):
    if kind not in ('relu', 'leaky_relu', 'tanh') or slope < 0:
        raise ValueError('activation')
    return [max(0, x) if kind == 'relu' else (x if x >= 0 else slope * x) if kind == 'leaky_relu' else math.tanh(x) for x in values]

def sigmoid(value):
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1 + exp)
