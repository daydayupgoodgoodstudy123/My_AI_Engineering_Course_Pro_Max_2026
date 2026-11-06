"""Original interview practice for 16-multi-agent-and-swarms/17-generative-agents-simulation.

Local source: phases/16-multi-agent-and-swarms/17-generative-agents-simulation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def markov_step(distribution, transition):
    n = len(distribution)
    if not n or len(transition) != n or any((len(r) != n for r in transition)) or any((p < 0 for r in [distribution] + transition for p in r)) or any((abs(sum(r) - 1) > 1e-09 for r in [distribution] + transition)):
        raise ValueError('stochastic matrix')
    return [sum((distribution[i] * transition[i][j] for i in range(n))) for j in range(n)]

def route_task(routes, query_tokens, role):
    if len({r['name'] for r in routes}) != len(routes):
        raise ValueError('duplicate route')
    scores = [(len(set(r['keywords']) & set(query_tokens)), r['name']) for r in routes if role in r['roles']]
    best = max((s for s, n in scores), default=0)
    names = [n for s, n in scores if s == best]
    return names[0] if best > 0 and len(names) == 1 else None
