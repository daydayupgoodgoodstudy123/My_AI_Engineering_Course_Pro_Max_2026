"""Original interview practice for 01-math-foundations/11-singular-value-decomposition.

Local source: phases/01-math-foundations/11-singular-value-decomposition/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def eigenvalues_2x2(matrix):
    """Require a 2x2 numeric matrix. Return its two real eigenvalues sorted ascending. A negative discriminant or invalid shape raises ValueError. Repeated eigenvalues appear twice."""
    raise NotImplementedError('TODO 1: eigenvalues_2x2; see PROMPT.md')

def solve_2x2(matrix, rhs):
    """Solve A*x=rhs using a 2x2 matrix and two-element rhs. Invalid shapes or abs(det)<1e-12 raises ValueError. Return [x0,x1]."""
    raise NotImplementedError('TODO 2: solve_2x2; see PROMPT.md')
