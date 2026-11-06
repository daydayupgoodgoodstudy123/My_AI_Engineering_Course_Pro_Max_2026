"""Original interview practice for 14-agent-engineering/09-hybrid-memory-mem0.

Local source: phases/14-agent-engineering/09-hybrid-memory-mem0/docs/en.md (sha256 in SCOPE.json).
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

def rrf(rankings, constant=60):
    if constant < 0:
        raise ValueError('constant')
    scores = {}
    for ranking in rankings:
        seen = set()
        for rank, item in enumerate(ranking, 1):
            if item not in seen:
                scores[item] = scores.get(item, 0) + 1 / (constant + rank)
                seen.add(item)
    return sorted(scores, key=lambda x: (-scores[x], x))
