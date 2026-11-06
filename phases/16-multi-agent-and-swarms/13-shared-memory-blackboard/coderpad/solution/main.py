"""Original interview practice for 16-multi-agent-and-swarms/13-shared-memory-blackboard.

Local source: phases/16-multi-agent-and-swarms/13-shared-memory-blackboard/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def compact_memory(records, limit):
    if type(limit) is not int or limit < 0:
        raise ValueError('limit')
    latest = {}
    for r in records:
        if r['id'] not in latest or r['timestamp'] >= latest[r['id']]['timestamp']:
            latest[r['id']] = r
    return copy.deepcopy(sorted(latest.values(), key=lambda r: (-r['timestamp'], r['id']))[:limit])

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
