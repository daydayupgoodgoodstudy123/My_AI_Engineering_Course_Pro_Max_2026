"""Original interview practice for 09-reinforcement-learning/11-sim-to-real-transfer.

Local source: phases/09-reinforcement-learning/11-sim-to-real-transfer/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def drift_report(baseline, current, tolerance):
    if set(baseline) != set(current) or tolerance < 0:
        raise ValueError('metrics')
    return sorted((k for k in baseline if abs(current[k] - baseline[k]) > tolerance))

def zscore_flags(values, threshold):
    if threshold < 0:
        raise ValueError('threshold')
    if not values:
        return []
    mean = sum(values) / len(values)
    sd = math.sqrt(sum(((x - mean) ** 2 for x in values)) / len(values))
    return [abs(x - mean) / sd > threshold if sd else False for x in values]
