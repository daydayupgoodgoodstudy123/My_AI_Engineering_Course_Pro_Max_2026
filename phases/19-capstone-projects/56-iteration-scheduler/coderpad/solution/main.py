"""Original interview practice for 19-capstone-projects/56-iteration-scheduler.

Local source: phases/19-capstone-projects/56-iteration-scheduler/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def select_ucb(means, visits, total, exploration):
    if not means or len(means) != len(visits) or type(total) is not int or (total < 1) or (exploration < 0) or any((type(v) is not int or v < 0 for v in visits)):
        raise ValueError('UCB')
    if 0 in visits:
        return visits.index(0)
    return max(range(len(means)), key=lambda i: means[i] + exploration * math.sqrt(math.log(total) / visits[i]))

def budget_decisions(costs, limit):
    if limit < 0 or any((c < 0 for c in costs)):
        raise ValueError('budget')
    spent = 0
    accepted = []
    for cost in costs:
        allow = spent + cost <= limit
        accepted.append(allow)
        if allow:
            spent += cost
    return {'accepted': accepted, 'spent': spent}
