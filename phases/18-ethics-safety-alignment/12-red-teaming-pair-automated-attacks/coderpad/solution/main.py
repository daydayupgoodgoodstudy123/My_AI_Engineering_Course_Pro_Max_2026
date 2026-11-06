"""Original interview practice for 18-ethics-safety-alignment/12-red-teaming-pair-automated-attacks.

Local source: phases/18-ethics-safety-alignment/12-red-teaming-pair-automated-attacks/docs/en.md (sha256 in SCOPE.json).
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

def prioritize_risks(risks):
    if len({r['id'] for r in risks}) != len(risks) or any((type(r[k]) is not int or not 1 <= r[k] <= 5 for r in risks for k in ('severity', 'likelihood'))):
        raise ValueError('risk')
    return [r['id'] for r in sorted(risks, key=lambda r: (-r['severity'] * r['likelihood'], -r['severity'], r['id']))]
