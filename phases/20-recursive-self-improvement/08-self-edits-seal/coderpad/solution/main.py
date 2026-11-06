"""Original interview practice for 20-recursive-self-improvement/08-self-edits-seal.

Local source: phases/20-recursive-self-improvement/08-self-edits-seal/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def gradient_step(weights, gradients, rate):
    if len(weights) != len(gradients) or rate < 0:
        raise ValueError('contract')
    return [w - rate * g for w, g in zip(weights, gradients)]

def quadratic_gradient(weights, target):
    if len(weights) != len(target):
        raise ValueError('shape')
    return [2 * (w - t) for w, t in zip(weights, target)]
