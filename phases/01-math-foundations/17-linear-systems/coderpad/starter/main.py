"""Original interview practice for 01-math-foundations/17-linear-systems.

Local source: phases/01-math-foundations/17-linear-systems/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def solve_2x2(matrix, rhs):
    """Solve A*x=rhs using a 2x2 matrix and two-element rhs. Invalid shapes or abs(det)<1e-12 raises ValueError. Return [x0,x1]."""
    raise NotImplementedError('TODO 1: solve_2x2; see PROMPT.md')

def matmul(a, b):
    """Multiply nonempty rectangular numeric matrices using row-by-column products. Reject empty matrices, ragged rows, empty rows or incompatible inner dimensions with ValueError."""
    raise NotImplementedError('TODO 2: matmul; see PROMPT.md')
