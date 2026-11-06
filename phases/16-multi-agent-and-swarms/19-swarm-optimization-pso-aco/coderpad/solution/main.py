"""Original interview practice for 16-multi-agent-and-swarms/19-swarm-optimization-pso-aco.

Local source: phases/16-multi-agent-and-swarms/19-swarm-optimization-pso-aco/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def top_k(scores, k):
    if type(k) is not int or not 0 <= k <= len(scores):
        raise ValueError('k')
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]

def pareto_front(candidates):
    return sorted((a['id'] for a in candidates if not any((b['quality'] >= a['quality'] and b['cost'] <= a['cost'] and (b['quality'] > a['quality'] or b['cost'] < a['cost']) for b in candidates))))
