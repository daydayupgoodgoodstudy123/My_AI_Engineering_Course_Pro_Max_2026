"""Original interview practice for 17-infrastructure-and-production/18-vllm-production-stack-lmcache.

Local source: phases/17-infrastructure-and-production/18-vllm-production-stack-lmcache/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


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
