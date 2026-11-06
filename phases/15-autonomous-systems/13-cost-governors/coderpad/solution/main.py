"""Original interview practice for 15-autonomous-systems/13-cost-governors.

Local source: phases/15-autonomous-systems/13-cost-governors/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


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

def token_cost(usage, prices):
    totals = {}
    for r in usage:
        pin, pout = prices[r['provider']]
        if pin < 0 or pout < 0 or any((type(r[k]) is not int or r[k] < 0 for k in ('input_tokens', 'output_tokens'))):
            raise ValueError('usage')
        totals[r['provider']] = totals.get(r['provider'], 0) + r['input_tokens'] * pin + r['output_tokens'] * pout
    return {'total': sum(totals.values()), 'by_provider': totals}
