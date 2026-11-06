"""Original interview practice for 00-setup-and-tooling/03-gpu-setup-and-cloud.

Local source: phases/00-setup-and-tooling/03-gpu-setup-and-cloud/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def parameter_memory(shapes, bytes_per_parameter):
    if type(bytes_per_parameter) is not int or bytes_per_parameter <= 0 or any((type(d) is not int or d <= 0 for shape in shapes for d in shape)):
        raise ValueError('shape')
    return sum((math.prod(shape) for shape in shapes)) * bytes_per_parameter

def amdahl(serial_fraction, speedup):
    if not 0 <= serial_fraction <= 1 or speedup < 1:
        raise ValueError('parameters')
    return 1 / (serial_fraction + (1 - serial_fraction) / speedup)
