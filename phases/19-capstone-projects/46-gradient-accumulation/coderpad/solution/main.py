"""Original interview practice for 19-capstone-projects/46-gradient-accumulation.

Local source: phases/19-capstone-projects/46-gradient-accumulation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def allreduce(vectors, average=False):
    if not vectors or any((len(v) != len(vectors[0]) for v in vectors)):
        raise ValueError('shape')
    return [sum(column) / (len(vectors) if average else 1) for column in zip(*vectors)]

def gradient_step(weights, gradients, rate):
    if len(weights) != len(gradients) or rate < 0:
        raise ValueError('contract')
    return [w - rate * g for w, g in zip(weights, gradients)]
