"""Original interview practice for 19-capstone-projects/77-data-parallel-ddp.

Local source: phases/19-capstone-projects/77-data-parallel-ddp/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def allreduce(vectors, average=False):
    """Require a nonempty list of equal-length numeric vectors. Return elementwise sum, or mean if average is True. Ragged/empty worker lists raise ValueError; zero-length worker vectors are valid. No networking."""
    raise NotImplementedError('TODO 1: allreduce; see PROMPT.md')

def quadratic_gradient(weights, target):
    """For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 2: quadratic_gradient; see PROMPT.md')
