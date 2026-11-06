"""Original interview practice for 15-autonomous-systems/22-cais-caisi-societal-risk.

Local source: phases/15-autonomous-systems/22-cais-caisi-societal-risk/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def prioritize_risks(risks):
    if len({r['id'] for r in risks}) != len(risks) or any((type(r[k]) is not int or not 1 <= r[k] <= 5 for r in risks for k in ('severity', 'likelihood'))):
        raise ValueError('risk')
    return [r['id'] for r in sorted(risks, key=lambda r: (-r['severity'] * r['likelihood'], -r['severity'], r['id']))]

def selection_gap(groups, selected):
    if not groups or len(groups) != len(selected) or any((type(x) is not bool for x in selected)):
        raise ValueError('groups')
    counts = Counter(groups)
    positives = Counter((g for g, s in zip(groups, selected) if s))
    rates = {g: positives[g] / n for g, n in sorted(counts.items())}
    return {'rates': rates, 'gap': max(rates.values()) - min(rates.values())}
