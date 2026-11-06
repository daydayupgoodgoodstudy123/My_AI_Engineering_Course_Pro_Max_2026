"""Original interview practice for 01-math-foundations/04-calculus-for-ml.

Local source: phases/01-math-foundations/04-calculus-for-ml/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def polynomial_derivative(coefficients, x):
    return sum((i * c * x ** (i - 1) for i, c in enumerate(coefficients) if i))

def quadratic_gradient(weights, target):
    if len(weights) != len(target):
        raise ValueError('shape')
    return [2 * (w - t) for w, t in zip(weights, target)]
