"""Original interview practice for 17-infrastructure-and-production/11-multi-region-kv-locality.

Local source: phases/17-infrastructure-and-production/11-multi-region-kv-locality/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def lru_keys(accesses, capacity):
    if type(capacity) is not int or capacity < 0:
        raise ValueError('capacity')
    keys = []
    for key in accesses:
        if key in keys:
            keys.remove(key)
        keys.append(key)
        if len(keys) > capacity:
            keys.pop(0)
    return keys

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
