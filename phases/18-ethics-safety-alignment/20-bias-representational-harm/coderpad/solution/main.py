"""Original interview practice for 18-ethics-safety-alignment/20-bias-representational-harm.

Local source: phases/18-ethics-safety-alignment/20-bias-representational-harm/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def selection_gap(groups, selected):
    if not groups or len(groups) != len(selected) or any((type(x) is not bool for x in selected)):
        raise ValueError('groups')
    counts = Counter(groups)
    positives = Counter((g for g, s in zip(groups, selected) if s))
    rates = {g: positives[g] / n for g, n in sorted(counts.items())}
    return {'rates': rates, 'gap': max(rates.values()) - min(rates.values())}

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
