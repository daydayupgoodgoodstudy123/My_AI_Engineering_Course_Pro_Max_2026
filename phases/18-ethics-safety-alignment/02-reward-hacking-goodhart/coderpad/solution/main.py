"""Original interview practice for 18-ethics-safety-alignment/02-reward-hacking-goodhart.

Local source: phases/18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def drift_report(baseline, current, tolerance):
    if set(baseline) != set(current) or tolerance < 0:
        raise ValueError('metrics')
    return sorted((k for k in baseline if abs(current[k] - baseline[k]) > tolerance))

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
