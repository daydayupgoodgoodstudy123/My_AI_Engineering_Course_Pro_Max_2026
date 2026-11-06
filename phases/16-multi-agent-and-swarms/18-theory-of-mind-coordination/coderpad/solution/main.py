"""Original interview practice for 16-multi-agent-and-swarms/18-theory-of-mind-coordination.

Local source: phases/16-multi-agent-and-swarms/18-theory-of-mind-coordination/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bayes(prior, likelihood_positive, likelihood_negative):
    if any((not 0 <= x <= 1 for x in (prior, likelihood_positive, likelihood_negative))):
        raise ValueError('probability')
    den = prior * likelihood_positive + (1 - prior) * likelihood_negative
    if den == 0:
        raise ValueError('impossible evidence')
    return prior * likelihood_positive / den

def route_task(routes, query_tokens, role):
    if len({r['name'] for r in routes}) != len(routes):
        raise ValueError('duplicate route')
    scores = [(len(set(r['keywords']) & set(query_tokens)), r['name']) for r in routes if role in r['roles']]
    best = max((s for s, n in scores), default=0)
    names = [n for s, n in scores if s == best]
    return names[0] if best > 0 and len(names) == 1 else None
