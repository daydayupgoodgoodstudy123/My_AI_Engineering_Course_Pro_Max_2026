"""Original interview practice for 17-infrastructure-and-production/14-prompt-semantic-caching.

Local source: phases/17-infrastructure-and-production/14-prompt-semantic-caching/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
import copy

def cosine(a, b):
    if len(a) != len(b):
        raise ValueError('shape')
    den = math.sqrt(sum((x * x for x in a)) * sum((y * y for y in b)))
    return sum((x * y for x, y in zip(a, b))) / den if den else 0

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
