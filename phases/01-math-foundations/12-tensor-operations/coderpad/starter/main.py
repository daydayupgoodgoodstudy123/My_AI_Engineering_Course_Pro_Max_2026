"""Original interview practice for 01-math-foundations/12-tensor-operations.

Local source: phases/01-math-foundations/12-tensor-operations/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def transpose(rows):
    """Return a new list-of-lists transpose. Empty input returns []. Ragged rows raise ValueError. A rectangular matrix of empty rows transposes to []."""
    raise NotImplementedError('TODO 1: transpose; see PROMPT.md')

def parameter_memory(shapes, bytes_per_parameter):
    """Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError."""
    raise NotImplementedError('TODO 2: parameter_memory; see PROMPT.md')
