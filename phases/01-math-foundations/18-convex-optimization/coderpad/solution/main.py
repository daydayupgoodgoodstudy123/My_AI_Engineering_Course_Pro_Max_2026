"""Original interview practice for 01-math-foundations/18-convex-optimization.

Local source: phases/01-math-foundations/18-convex-optimization/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def eigenvalues_2x2(matrix):
    if len(matrix) != 2 or any((len(r) != 2 for r in matrix)):
        raise ValueError('shape')
    a, b = matrix[0]
    c, d = matrix[1]
    disc = (a + d) ** 2 - 4 * (a * d - b * c)
    if disc < 0:
        raise ValueError('complex roots')
    return [(a + d - math.sqrt(disc)) / 2, (a + d + math.sqrt(disc)) / 2]

def quadratic_gradient(weights, target):
    if len(weights) != len(target):
        raise ValueError('shape')
    return [2 * (w - t) for w, t in zip(weights, target)]
