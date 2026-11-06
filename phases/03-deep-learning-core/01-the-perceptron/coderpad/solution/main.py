"""Original interview practice for 03-deep-learning-core/01-the-perceptron.

Local source: phases/03-deep-learning-core/01-the-perceptron/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def linear(features, weights, bias):
    if len(weights) != len(bias) or any((len(r) != len(features) for r in weights)):
        raise ValueError('shape')
    return [sum((x * w for x, w in zip(features, row))) + b for row, b in zip(weights, bias)]

def activation(values, kind='relu', slope=0.01):
    if kind not in ('relu', 'leaky_relu', 'tanh') or slope < 0:
        raise ValueError('activation')
    return [max(0, x) if kind == 'relu' else (x if x >= 0 else slope * x) if kind == 'leaky_relu' else math.tanh(x) for x in values]
