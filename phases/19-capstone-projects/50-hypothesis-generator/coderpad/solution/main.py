"""Original interview practice for 19-capstone-projects/50-hypothesis-generator.

Local source: phases/19-capstone-projects/50-hypothesis-generator/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def select_context(items, budget):
    if type(budget) is not int or budget < 0 or any((type(x['tokens']) is not int or x['tokens'] < 0 for x in items)):
        raise ValueError('budget')
    result = []
    for item in sorted(items, key=lambda x: (-x['score'], x['id'])):
        if item['tokens'] <= budget:
            result.append(item['id'])
            budget -= item['tokens']
    return result

def pareto_front(candidates):
    return sorted((a['id'] for a in candidates if not any((b['quality'] >= a['quality'] and b['cost'] <= a['cost'] and (b['quality'] > a['quality'] or b['cost'] < a['cost']) for b in candidates))))
