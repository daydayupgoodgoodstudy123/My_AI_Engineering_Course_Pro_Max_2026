"""Original interview practice for 20-recursive-self-improvement/09-self-improving-scaffolds-stop-promptbreeder-adas.

Local source: phases/20-recursive-self-improvement/09-self-improving-scaffolds-stop-promptbreeder-adas/code/main.py (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def pareto_front(candidates):
    return sorted((a['id'] for a in candidates if not any((b['quality'] >= a['quality'] and b['cost'] <= a['cost'] and (b['quality'] > a['quality'] or b['cost'] < a['cost']) for b in candidates))))

def select_ucb(means, visits, total, exploration):
    if not means or len(means) != len(visits) or type(total) is not int or (total < 1) or (exploration < 0) or any((type(v) is not int or v < 0 for v in visits)):
        raise ValueError('UCB')
    if 0 in visits:
        return visits.index(0)
    return max(range(len(means)), key=lambda i: means[i] + exploration * math.sqrt(math.log(total) / visits[i]))
