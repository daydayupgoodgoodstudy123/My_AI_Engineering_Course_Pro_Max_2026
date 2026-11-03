"""Original Phase 13 / Lesson 25 CoderPad practice.

Lesson source: 25-skill-invocation-and-routing/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import re

def route(skills, query, actor, explicit=None):
    if actor not in ('human', 'model'):
        raise ValueError('actor')
    eligible = [s for s in skills if s[actor]]
    if explicit is not None:
        return {'name': explicit, 'reason': 'explicit'} if any((s['name'] == explicit for s in eligible)) else {'name': None, 'reason': 'ineligible'}
    tokens = set(re.findall('[a-z0-9]+', query.casefold()))
    scores = [(len(tokens & s['keywords']), s['name']) for s in eligible]
    best = max((x[0] for x in scores), default=0)
    if best == 0:
        return {'name': None, 'reason': 'no_match'}
    names = [n for score, n in scores if score == best]
    return {'name': names[0], 'reason': 'matched'} if len(names) == 1 else {'name': None, 'reason': 'ambiguous'}

def matrix(skills):
    return {actor: sorted((s['name'] for s in skills if s[actor])) for actor in ('human', 'model')}
