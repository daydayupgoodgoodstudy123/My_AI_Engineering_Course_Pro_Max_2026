"""Original interview practice for 11-llm-engineering/05-context-engineering.

Local source: phases/11-llm-engineering/05-context-engineering/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def select_context(items, budget):
    if type(budget) is not int or budget < 0 or any((type(x['tokens']) is not int or x['tokens'] < 0 for x in items)):
        raise ValueError('budget')
    result = []
    for item in sorted(items, key=lambda x: (-x['score'], x['id'])):
        if item['tokens'] <= budget:
            result.append(item['id'])
            budget -= item['tokens']
    return result

def compact_memory(records, limit):
    if type(limit) is not int or limit < 0:
        raise ValueError('limit')
    latest = {}
    for r in records:
        if r['id'] not in latest or r['timestamp'] >= latest[r['id']]['timestamp']:
            latest[r['id']] = r
    return copy.deepcopy(sorted(latest.values(), key=lambda r: (-r['timestamp'], r['id']))[:limit])
