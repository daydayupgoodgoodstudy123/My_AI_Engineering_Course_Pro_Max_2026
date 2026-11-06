"""Original interview practice for 03-deep-learning-core/10-mini-framework.

Local source: phases/03-deep-learning-core/10-mini-framework/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def linear(features, weights, bias):
    if len(weights) != len(bias) or any((len(r) != len(features) for r in weights)):
        raise ValueError('shape')
    return [sum((x * w for x, w in zip(features, row))) + b for row, b in zip(weights, bias)]

def quadratic_gradient(weights, target):
    if len(weights) != len(target):
        raise ValueError('shape')
    return [2 * (w - t) for w, t in zip(weights, target)]
