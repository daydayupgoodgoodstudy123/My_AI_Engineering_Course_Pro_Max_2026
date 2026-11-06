"""Original interview practice for 01-math-foundations/03-matrix-transformations.

Local source: phases/01-math-foundations/03-matrix-transformations/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def transform(points, matrix, offset):
    if len(matrix) != 2 or any((len(r) != 2 for r in matrix)) or len(offset) != 2 or any((len(p) != 2 for p in points)):
        raise ValueError('shape')
    return [[sum((matrix[i][j] * p[j] for j in range(2))) + offset[i] for i in range(2)] for p in points]

def eigenvalues_2x2(matrix):
    if len(matrix) != 2 or any((len(r) != 2 for r in matrix)):
        raise ValueError('shape')
    a, b = matrix[0]
    c, d = matrix[1]
    disc = (a + d) ** 2 - 4 * (a * d - b * c)
    if disc < 0:
        raise ValueError('complex roots')
    return [(a + d - math.sqrt(disc)) / 2, (a + d + math.sqrt(disc)) / 2]
