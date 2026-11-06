"""Original interview practice for 02-ml-fundamentals/02-linear-regression.

Local source: phases/02-ml-fundamentals/02-linear-regression/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def linear(features, weights, bias):
    if len(weights) != len(bias) or any((len(r) != len(features) for r in weights)):
        raise ValueError('shape')
    return [sum((x * w for x, w in zip(features, row))) + b for row, b in zip(weights, bias)]

def mse(predicted, expected):
    if not predicted or len(predicted) != len(expected):
        raise ValueError('shape')
    return sum(((a - b) ** 2 for a, b in zip(predicted, expected))) / len(predicted)
