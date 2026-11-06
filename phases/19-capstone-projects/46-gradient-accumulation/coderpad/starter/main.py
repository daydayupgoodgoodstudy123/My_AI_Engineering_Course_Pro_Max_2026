"""Original interview practice for 19-capstone-projects/46-gradient-accumulation.

Local source: phases/19-capstone-projects/46-gradient-accumulation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def allreduce(vectors, average=False):
    """Require a nonempty list of equal-length numeric vectors. Return elementwise sum, or mean if average is True. Ragged/empty worker lists raise ValueError; zero-length worker vectors are valid. No networking."""
    raise NotImplementedError('TODO 1: allreduce; see PROMPT.md')

def gradient_step(weights, gradients, rate):
    """Return w-rate*g for equal-length numeric vectors and rate>=0. Unequal lengths or negative rate raises ValueError. Preserve inputs; empty vectors are valid."""
    raise NotImplementedError('TODO 2: gradient_step; see PROMPT.md')
