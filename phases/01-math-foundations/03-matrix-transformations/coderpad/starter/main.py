"""Original interview practice for 01-math-foundations/03-matrix-transformations.

Local source: phases/01-math-foundations/03-matrix-transformations/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def transform(points, matrix, offset):
    """Apply 2x2 matrix and 2D offset to each 2D point. Return a new list of transformed points. Invalid matrix, offset, or point shapes raise ValueError. Empty points returns []."""
    raise NotImplementedError('TODO 1: transform; see PROMPT.md')

def eigenvalues_2x2(matrix):
    """Require a 2x2 numeric matrix. Return its two real eigenvalues sorted ascending. A negative discriminant or invalid shape raises ValueError. Repeated eigenvalues appear twice."""
    raise NotImplementedError('TODO 2: eigenvalues_2x2; see PROMPT.md')
