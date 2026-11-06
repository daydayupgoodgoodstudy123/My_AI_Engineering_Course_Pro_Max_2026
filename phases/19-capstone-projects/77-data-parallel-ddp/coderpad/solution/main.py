"""Original interview practice for 19-capstone-projects/77-data-parallel-ddp.

Local source: phases/19-capstone-projects/77-data-parallel-ddp/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def allreduce(vectors, average=False):
    if not vectors or any((len(v) != len(vectors[0]) for v in vectors)):
        raise ValueError('shape')
    return [sum(column) / (len(vectors) if average else 1) for column in zip(*vectors)]

def quadratic_gradient(weights, target):
    if len(weights) != len(target):
        raise ValueError('shape')
    return [2 * (w - t) for w, t in zip(weights, target)]
