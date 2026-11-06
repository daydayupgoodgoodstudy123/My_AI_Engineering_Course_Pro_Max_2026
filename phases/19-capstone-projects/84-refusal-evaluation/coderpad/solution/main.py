"""Original interview practice for 19-capstone-projects/84-refusal-evaluation.

Local source: phases/19-capstone-projects/84-refusal-evaluation/docs/en.md (sha256 in SCOPE.json).
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

def moderation(signals, block_at):
    if type(block_at) is not int or not 0 <= block_at <= 3 or any((type(s['severity']) is not int or not 0 <= s['severity'] <= 3 for s in signals)):
        raise ValueError('severity')
    categories = {}
    for s in signals:
        categories[s['category']] = max(categories.get(s['category'], 0), s['severity'])
    return {'categories': dict(sorted(categories.items())), 'blocked': any((v >= block_at for v in categories.values()))}
