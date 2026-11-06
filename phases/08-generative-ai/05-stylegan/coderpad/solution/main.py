"""Original interview practice for 08-generative-ai/05-stylegan.

Local source: phases/08-generative-ai/05-stylegan/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def summary(values):
    if not values:
        raise ValueError('empty')
    mean = sum(values) / len(values)
    return {'mean': mean, 'variance': sum(((x - mean) ** 2 for x in values)) / len(values), 'min': min(values), 'max': max(values)}

def linear(features, weights, bias):
    if len(weights) != len(bias) or any((len(r) != len(features) for r in weights)):
        raise ValueError('shape')
    return [sum((x * w for x, w in zip(features, row))) + b for row, b in zip(weights, bias)]
