"""Original interview practice for 19-capstone-projects/34-transformer-block.

Local source: phases/19-capstone-projects/34-transformer-block/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def layer_norm(values, epsilon=1e-05):
    if not values or epsilon <= 0:
        raise ValueError('contract')
    mean = sum(values) / len(values)
    variance = sum(((x - mean) ** 2 for x in values)) / len(values)
    return [(x - mean) / math.sqrt(variance + epsilon) for x in values]

def activation(values, kind='relu', slope=0.01):
    if kind not in ('relu', 'leaky_relu', 'tanh') or slope < 0:
        raise ValueError('activation')
    return [max(0, x) if kind == 'relu' else (x if x >= 0 else slope * x) if kind == 'leaky_relu' else math.tanh(x) for x in values]
