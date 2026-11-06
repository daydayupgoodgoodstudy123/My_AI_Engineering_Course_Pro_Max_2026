"""Original interview practice for 17-infrastructure-and-production/07-tensorrt-llm-blackwell.

Local source: phases/17-infrastructure-and-production/07-tensorrt-llm-blackwell/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def quantize(values, bits):
    if type(bits) is not int or not 2 <= bits <= 8:
        raise ValueError('bits')
    bound = 2 ** (bits - 1) - 1
    maximum = max((abs(x) for x in values), default=0)
    scale = maximum / bound if maximum else 1
    return {'values': [max(-bound, min(bound, round(x / scale))) for x in values], 'scale': scale}

def parameter_memory(shapes, bytes_per_parameter):
    if type(bytes_per_parameter) is not int or bytes_per_parameter <= 0 or any((type(d) is not int or d <= 0 for shape in shapes for d in shape)):
        raise ValueError('shape')
    return sum((math.prod(shape) for shape in shapes)) * bytes_per_parameter
