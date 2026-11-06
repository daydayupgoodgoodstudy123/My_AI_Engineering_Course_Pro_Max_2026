"""Original interview practice for 19-capstone-projects/37-loading-pretrained-weights.

Local source: phases/19-capstone-projects/37-loading-pretrained-weights/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
import hashlib

def manifest(files):
    if any((p.startswith('/') or '..' in p.split('/') for p in files)):
        raise ValueError('path')
    return {p: hashlib.sha256(files[p].encode()).hexdigest() for p in sorted(files)}

def parameter_memory(shapes, bytes_per_parameter):
    if type(bytes_per_parameter) is not int or bytes_per_parameter <= 0 or any((type(d) is not int or d <= 0 for shape in shapes for d in shape)):
        raise ValueError('shape')
    return sum((math.prod(shape) for shape in shapes)) * bytes_per_parameter
