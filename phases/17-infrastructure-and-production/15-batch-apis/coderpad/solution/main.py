"""Original interview practice for 17-infrastructure-and-production/15-batch-apis.

Local source: phases/17-infrastructure-and-production/15-batch-apis/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def make_batches(items, maximum):
    if type(maximum) is not int or maximum <= 0 or any((type(x['tokens']) is not int or not 0 < x['tokens'] <= maximum for x in items)):
        raise ValueError('batch')
    result = []
    current = []
    size = 0
    for x in items:
        if size + x['tokens'] > maximum:
            result.append(current)
            current = []
            size = 0
        current.append(x['id'])
        size += x['tokens']
    if current:
        result.append(current)
    return result

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
