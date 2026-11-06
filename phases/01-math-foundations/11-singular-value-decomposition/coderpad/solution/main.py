"""Original interview practice for 01-math-foundations/11-singular-value-decomposition.

Local source: phases/01-math-foundations/11-singular-value-decomposition/docs/en.md (sha256 in SCOPE.json).
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

def solve_2x2(matrix, rhs):
    if len(matrix) != 2 or any((len(r) != 2 for r in matrix)) or len(rhs) != 2:
        raise ValueError('shape')
    a, b = matrix[0]
    c, d = matrix[1]
    det = a * d - b * c
    if abs(det) < 1e-12:
        raise ValueError('singular')
    return [(rhs[0] * d - b * rhs[1]) / det, (a * rhs[1] - rhs[0] * c) / det]
