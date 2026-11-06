"""Original interview practice for 18-ethics-safety-alignment/21-fairness-criteria-group-individual-counterfactual.

Local source: phases/18-ethics-safety-alignment/21-fairness-criteria-group-individual-counterfactual/docs/en.md (sha256 in SCOPE.json).
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

def calibration_error(confidences, correct, bins):
    if not confidences or len(confidences) != len(correct) or type(bins) is not int or (bins <= 0) or any((not 0 <= p <= 1 for p in confidences)) or any((type(x) is not bool for x in correct)):
        raise ValueError('calibration')
    groups = {}
    for p, c in zip(confidences, correct):
        groups.setdefault(min(bins - 1, int(p * bins)), []).append((p, c))
    return sum((abs(sum((p for p, c in group)) - sum((c for p, c in group))) / len(confidences) for group in groups.values()))
