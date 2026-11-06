"""Original interview practice for 19-capstone-projects/32-token-positional-embeddings.

Local source: phases/19-capstone-projects/32-token-positional-embeddings/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def position_encoding(position, dimensions):
    if position < 0 or type(dimensions) is not int or dimensions <= 0 or dimensions % 2:
        raise ValueError('dimensions')
    result = []
    for i in range(dimensions // 2):
        angle = position / 10000 ** (2 * i / dimensions)
        result.extend([math.sin(angle), math.cos(angle)])
    return result

def linear(features, weights, bias):
    if len(weights) != len(bias) or any((len(r) != len(features) for r in weights)):
        raise ValueError('shape')
    return [sum((x * w for x, w in zip(features, row))) + b for row, b in zip(weights, bias)]
