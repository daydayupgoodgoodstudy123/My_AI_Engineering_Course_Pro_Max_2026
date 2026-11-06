"""Original interview practice for 18-ethics-safety-alignment/22-differential-privacy-for-llms.

Local source: phases/18-ethics-safety-alignment/22-differential-privacy-for-llms/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def privacy_budget(epsilons, deltas, max_epsilon, max_delta):
    if len(epsilons) != len(deltas) or any((x < 0 for x in epsilons + deltas + [max_epsilon, max_delta])):
        raise ValueError('budget')
    e, d = (sum(epsilons), sum(deltas))
    return {'epsilon': e, 'delta': d, 'within_budget': e <= max_epsilon and d <= max_delta}

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
