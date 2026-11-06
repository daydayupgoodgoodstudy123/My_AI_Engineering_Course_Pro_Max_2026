"""Original interview practice for 01-math-foundations/04-calculus-for-ml.

Local source: phases/01-math-foundations/04-calculus-for-ml/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def polynomial_derivative(coefficients, x):
    """coefficients[i] multiplies x**i. Return the derivative at x, with [] and constant polynomials returning 0. Inputs are finite numbers."""
    raise NotImplementedError('TODO 1: polynomial_derivative; see PROMPT.md')

def quadratic_gradient(weights, target):
    """For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 2: quadratic_gradient; see PROMPT.md')
