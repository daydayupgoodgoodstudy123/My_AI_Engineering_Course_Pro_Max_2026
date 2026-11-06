"""Original interview practice for 17-infrastructure-and-production/12-edge-inference.

Local source: phases/17-infrastructure-and-production/12-edge-inference/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def parameter_memory(shapes, bytes_per_parameter):
    """Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError."""
    raise NotImplementedError('TODO 1: parameter_memory; see PROMPT.md')

def quantize(values, bits):
    """bits must be exact int 2..8. Set bound=2**(bits-1)-1, scale=max(abs(values))/bound (or 1 for empty/all-zero input). Return {'values':[rounded x/scale clipped to -bound..bound], 'scale':scale}. Python round (ties to even) defines rounding."""
    raise NotImplementedError('TODO 2: quantize; see PROMPT.md')
