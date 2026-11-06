"""Original interview practice for 19-capstone-projects/78-zero-parameter-sharding.

Local source: phases/19-capstone-projects/78-zero-parameter-sharding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def shard_bounds(total, workers):
    if type(total) is not int or type(workers) is not int or total < 0 or (workers <= 0):
        raise ValueError('shape')
    q, r = divmod(total, workers)
    start = 0
    result = []
    for i in range(workers):
        end = start + q + (i < r)
        result.append([start, end])
        start = end
    return result

def parameter_memory(shapes, bytes_per_parameter):
    if type(bytes_per_parameter) is not int or bytes_per_parameter <= 0 or any((type(d) is not int or d <= 0 for shape in shapes for d in shape)):
        raise ValueError('shape')
    return sum((math.prod(shape) for shape in shapes)) * bytes_per_parameter
