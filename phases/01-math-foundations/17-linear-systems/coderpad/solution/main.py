"""Original interview practice for 01-math-foundations/17-linear-systems.

Local source: phases/01-math-foundations/17-linear-systems/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def solve_2x2(matrix, rhs):
    if len(matrix) != 2 or any((len(r) != 2 for r in matrix)) or len(rhs) != 2:
        raise ValueError('shape')
    a, b = matrix[0]
    c, d = matrix[1]
    det = a * d - b * c
    if abs(det) < 1e-12:
        raise ValueError('singular')
    return [(rhs[0] * d - b * rhs[1]) / det, (a * rhs[1] - rhs[0] * c) / det]

def matmul(a, b):
    if not a or not b or (not a[0]) or (not b[0]) or any((len(r) != len(a[0]) for r in a)) or any((len(r) != len(b[0]) for r in b)) or (len(a[0]) != len(b)):
        raise ValueError('shape')
    return [[sum((a[i][k] * b[k][j] for k in range(len(b)))) for j in range(len(b[0]))] for i in range(len(a))]
