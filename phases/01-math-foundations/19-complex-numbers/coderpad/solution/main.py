"""Original interview practice for 01-math-foundations/19-complex-numbers.

Local source: phases/01-math-foundations/19-complex-numbers/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dft(samples):
    n = len(samples)
    return [[sum((x * math.cos(-2 * math.pi * k * j / n) for j, x in enumerate(samples))), sum((x * math.sin(-2 * math.pi * k * j / n) for j, x in enumerate(samples)))] for k in range(n)]

def transform(points, matrix, offset):
    if len(matrix) != 2 or any((len(r) != 2 for r in matrix)) or len(offset) != 2 or any((len(p) != 2 for p in points)):
        raise ValueError('shape')
    return [[sum((matrix[i][j] * p[j] for j in range(2))) + offset[i] for i in range(2)] for p in points]
