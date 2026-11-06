"""Original interview practice for 02-ml-fundamentals/16-anomaly-detection.

Local source: phases/02-ml-fundamentals/16-anomaly-detection/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def zscore_flags(values, threshold):
    if threshold < 0:
        raise ValueError('threshold')
    if not values:
        return []
    mean = sum(values) / len(values)
    sd = math.sqrt(sum(((x - mean) ** 2 for x in values)) / len(values))
    return [abs(x - mean) / sd > threshold if sd else False for x in values]

def summary(values):
    if not values:
        raise ValueError('empty')
    mean = sum(values) / len(values)
    return {'mean': mean, 'variance': sum(((x - mean) ** 2 for x in values)) / len(values), 'min': min(values), 'max': max(values)}
