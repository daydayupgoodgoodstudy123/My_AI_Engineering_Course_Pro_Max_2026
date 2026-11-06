"""Original interview practice for 17-infrastructure-and-production/28-self-hosted-serving-selection.

Local source: phases/17-infrastructure-and-production/28-self-hosted-serving-selection/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def pareto_front(candidates):
    return sorted((a['id'] for a in candidates if not any((b['quality'] >= a['quality'] and b['cost'] <= a['cost'] and (b['quality'] > a['quality'] or b['cost'] < a['cost']) for b in candidates))))

def parameter_memory(shapes, bytes_per_parameter):
    if type(bytes_per_parameter) is not int or bytes_per_parameter <= 0 or any((type(d) is not int or d <= 0 for shape in shapes for d in shape)):
        raise ValueError('shape')
    return sum((math.prod(shape) for shape in shapes)) * bytes_per_parameter
