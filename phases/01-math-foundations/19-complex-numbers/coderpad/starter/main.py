"""Original interview practice for 01-math-foundations/19-complex-numbers.

Local source: phases/01-math-foundations/19-complex-numbers/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dft(samples):
    """Compute unnormalized forward DFT of real samples using exp(-2*pi*i*k*n/N). Return one [real,imaginary] pair per frequency bin. Empty input returns []. No FFT library."""
    raise NotImplementedError('TODO 1: dft; see PROMPT.md')

def transform(points, matrix, offset):
    """Apply 2x2 matrix and 2D offset to each 2D point. Return a new list of transformed points. Invalid matrix, offset, or point shapes raise ValueError. Empty points returns []."""
    raise NotImplementedError('TODO 2: transform; see PROMPT.md')
