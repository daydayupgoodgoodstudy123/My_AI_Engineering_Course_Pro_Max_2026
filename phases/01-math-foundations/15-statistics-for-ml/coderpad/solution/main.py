"""Original interview practice for 01-math-foundations/15-statistics-for-ml.

Local source: phases/01-math-foundations/15-statistics-for-ml/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def summary(values):
    if not values:
        raise ValueError('empty')
    mean = sum(values) / len(values)
    return {'mean': mean, 'variance': sum(((x - mean) ** 2 for x in values)) / len(values), 'min': min(values), 'max': max(values)}

def calibration_error(confidences, correct, bins):
    if not confidences or len(confidences) != len(correct) or type(bins) is not int or (bins <= 0) or any((not 0 <= p <= 1 for p in confidences)) or any((type(x) is not bool for x in correct)):
        raise ValueError('calibration')
    groups = {}
    for p, c in zip(confidences, correct):
        groups.setdefault(min(bins - 1, int(p * bins)), []).append((p, c))
    return sum((abs(sum((p for p, c in group)) - sum((c for p, c in group))) / len(confidences) for group in groups.values()))
