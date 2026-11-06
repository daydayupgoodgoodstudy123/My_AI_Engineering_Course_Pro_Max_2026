"""Original interview practice for 17-infrastructure-and-production/21-ab-testing-llm-features.

Local source: phases/17-infrastructure-and-production/21-ab-testing-llm-features/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def classification(expected, predicted):
    if len(expected) != len(predicted) or any((type(x) is not bool for x in expected + predicted)):
        raise ValueError('labels')
    tp = sum((a and b for a, b in zip(expected, predicted)))
    fp = sum((not a and b for a, b in zip(expected, predicted)))
    fn = sum((a and (not b) for a, b in zip(expected, predicted)))
    tn = len(expected) - tp - fp - fn
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'precision': p, 'recall': r, 'f1': 2 * p * r / (p + r) if p + r else 0}

def calibration_error(confidences, correct, bins):
    if not confidences or len(confidences) != len(correct) or type(bins) is not int or (bins <= 0) or any((not 0 <= p <= 1 for p in confidences)) or any((type(x) is not bool for x in correct)):
        raise ValueError('calibration')
    groups = {}
    for p, c in zip(confidences, correct):
        groups.setdefault(min(bins - 1, int(p * bins)), []).append((p, c))
    return sum((abs(sum((p for p, c in group)) - sum((c for p, c in group))) / len(confidences) for group in groups.values()))
