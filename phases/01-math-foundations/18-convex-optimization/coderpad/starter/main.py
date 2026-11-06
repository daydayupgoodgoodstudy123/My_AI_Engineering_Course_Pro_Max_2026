"""Original interview practice for 01-math-foundations/18-convex-optimization.

Local source: phases/01-math-foundations/18-convex-optimization/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def eigenvalues_2x2(matrix):
    """Require a 2x2 numeric matrix. Return its two real eigenvalues sorted ascending. A negative discriminant or invalid shape raises ValueError. Repeated eigenvalues appear twice."""
    raise NotImplementedError('TODO 1: eigenvalues_2x2; see PROMPT.md')

def quadratic_gradient(weights, target):
    """For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 2: quadratic_gradient; see PROMPT.md')
