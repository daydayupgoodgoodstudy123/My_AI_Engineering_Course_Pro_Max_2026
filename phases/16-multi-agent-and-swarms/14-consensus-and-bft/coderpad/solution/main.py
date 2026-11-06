"""Original interview practice for 16-multi-agent-and-swarms/14-consensus-and-bft.

Local source: phases/16-multi-agent-and-swarms/14-consensus-and-bft/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def quorum_vote(votes, members, required):
    if type(required) is not int or not len(members) / 2 < required <= len(members):
        raise ValueError('quorum')
    seen = {}
    for member, value in votes:
        if member not in members or (member in seen and seen[member] != value):
            raise ValueError('vote')
        seen[member] = value
    counts = Counter(seen.values())
    return next((v for v, n in counts.items() if n >= required), None)

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
