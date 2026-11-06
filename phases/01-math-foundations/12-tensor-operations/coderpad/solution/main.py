"""Original interview practice for 01-math-foundations/12-tensor-operations.

Local source: phases/01-math-foundations/12-tensor-operations/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def transpose(rows):
    if not rows:
        return []
    if any((len(r) != len(rows[0]) for r in rows)):
        raise ValueError('ragged')
    return [list(c) for c in zip(*rows)]

def parameter_memory(shapes, bytes_per_parameter):
    if type(bytes_per_parameter) is not int or bytes_per_parameter <= 0 or any((type(d) is not int or d <= 0 for shape in shapes for d in shape)):
        raise ValueError('shape')
    return sum((math.prod(shape) for shape in shapes)) * bytes_per_parameter
