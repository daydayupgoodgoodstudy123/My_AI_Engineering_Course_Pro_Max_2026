"""Original interview practice for 11-llm-engineering/11-caching-cost.

Local source: phases/11-llm-engineering/11-caching-cost/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def cache_replay(events, ttl):
    if ttl < 0:
        raise ValueError('ttl')
    cache = {}
    output = []
    for e in events:
        if e['op'] == 'put':
            cache[e['key']] = (e['time'] + ttl, copy.deepcopy(e['value']))
        elif e['op'] == 'get':
            entry = cache.get(e['key'])
            output.append(copy.deepcopy(entry[1]) if entry is not None and e['time'] < entry[0] else None)
        else:
            raise ValueError('operation')
    return output

def token_cost(usage, prices):
    totals = {}
    for r in usage:
        pin, pout = prices[r['provider']]
        if pin < 0 or pout < 0 or any((type(r[k]) is not int or r[k] < 0 for k in ('input_tokens', 'output_tokens'))):
            raise ValueError('usage')
        totals[r['provider']] = totals.get(r['provider'], 0) + r['input_tokens'] * pin + r['output_tokens'] * pout
    return {'total': sum(totals.values()), 'by_provider': totals}
