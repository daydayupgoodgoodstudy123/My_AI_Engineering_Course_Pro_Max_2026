"""Original interview practice for 03-deep-learning-core/11-intro-to-pytorch.

Local source: phases/03-deep-learning-core/11-intro-to-pytorch/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def parameter_memory(shapes, bytes_per_parameter):
    if type(bytes_per_parameter) is not int or bytes_per_parameter <= 0 or any((type(d) is not int or d <= 0 for shape in shapes for d in shape)):
        raise ValueError('shape')
    return sum((math.prod(shape) for shape in shapes)) * bytes_per_parameter

def make_batches(items, maximum):
    if type(maximum) is not int or maximum <= 0 or any((type(x['tokens']) is not int or not 0 < x['tokens'] <= maximum for x in items)):
        raise ValueError('batch')
    result = []
    current = []
    size = 0
    for x in items:
        if size + x['tokens'] > maximum:
            result.append(current)
            current = []
            size = 0
        current.append(x['id'])
        size += x['tokens']
    if current:
        result.append(current)
    return result
