"""Original interview practice for 03-deep-learning-core/03-backpropagation.

Local source: phases/03-deep-learning-core/03-backpropagation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def quadratic_gradient(weights, target):
    """For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 1: quadratic_gradient; see PROMPT.md')

def polynomial_derivative(coefficients, x):
    """coefficients[i] multiplies x**i. Return the derivative at x, with [] and constant polynomials returning 0. Inputs are finite numbers."""
    raise NotImplementedError('TODO 2: polynomial_derivative; see PROMPT.md')
