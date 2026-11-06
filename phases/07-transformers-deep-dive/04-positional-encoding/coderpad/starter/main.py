"""Original interview practice for 07-transformers-deep-dive/04-positional-encoding.

Local source: phases/07-transformers-deep-dive/04-positional-encoding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def position_encoding(position, dimensions):
    """dimensions is exact positive even int and position is numeric >=0. Return sin(position/10000**(2*i/dimensions)) then cos of the same angle for i=0..dimensions/2-1, interleaved. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: position_encoding; see PROMPT.md')

def transform(points, matrix, offset):
    """Apply 2x2 matrix and 2D offset to each 2D point. Return a new list of transformed points. Invalid matrix, offset, or point shapes raise ValueError. Empty points returns []."""
    raise NotImplementedError('TODO 2: transform; see PROMPT.md')
