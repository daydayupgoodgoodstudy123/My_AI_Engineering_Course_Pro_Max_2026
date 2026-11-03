"""Original Phase 13 / Lesson 24 CoderPad practice.

Lesson source: 24-skill-discovery-and-progressive-disclosure/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
from pathlib import Path

def catalog(candidates, precedence, budget):
    ranks = {s: i for i, s in enumerate(precedence)}
    groups = {}
    for c in candidates:
        if c['scope'] in ranks:
            groups.setdefault(c['name'], []).append(c)
    winners = []
    for name, items in sorted(groups.items()):
        rank = min((ranks[c['scope']] for c in items))
        best = [c for c in items if ranks[c['scope']] == rank]
        if len(best) != 1:
            raise ValueError('collision')
        winners.append(best[0])
    result = []
    for c in winners:
        cost = len(c['name']) + len(c['description'])
        if cost <= budget:
            result.append({'name': c['name'], 'description': c['description']})
            budget -= cost
    return result

def reference(root, relative, max_chars):
    root = Path(root).resolve()
    p = Path(relative)
    if p.is_absolute():
        raise ValueError('absolute')
    p = (root / p).resolve()
    if p != root and root not in p.parents:
        raise ValueError('escape')
    return p.read_text(encoding='utf-8')[:max_chars]

def activation(entry, body):
    return {'name': entry['name'], 'instructions': body}
