"""Original interview practice for 03-deep-learning-core/12-intro-to-jax.

Local source: phases/03-deep-learning-core/12-intro-to-jax/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def quadratic_gradient(weights, target):
    """For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 1: quadratic_gradient; see PROMPT.md')

def matmul(a, b):
    """Multiply nonempty rectangular numeric matrices using row-by-column products. Reject empty matrices, ragged rows, empty rows or incompatible inner dimensions with ValueError."""
    raise NotImplementedError('TODO 2: matmul; see PROMPT.md')
