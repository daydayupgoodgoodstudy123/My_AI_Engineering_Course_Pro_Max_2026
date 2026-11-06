"""Original interview practice for 10-llms-from-scratch/22-async-hogwild-inference.

Local source: phases/10-llms-from-scratch/22-async-hogwild-inference/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
from collections import deque

def replay_requests(requests):
    seen = {}
    executed = []
    replayed = []
    for r in requests:
        payload = json.dumps(r['payload'], sort_keys=True, separators=(',', ':'))
        if r['id'] in seen:
            if seen[r['id']] != payload:
                raise ValueError('conflict')
            replayed.append(r['id'])
        else:
            seen[r['id']] = payload
            executed.append(r['id'])
    return {'executed': executed, 'replayed': replayed}

def rate_limit(times, window, maximum):
    if window <= 0 or type(maximum) is not int or maximum <= 0 or any((a > b for a, b in zip(times, times[1:]))):
        raise ValueError('limiter')
    accepted = deque()
    result = []
    for now in times:
        while accepted and accepted[0] <= now - window:
            accepted.popleft()
        allow = len(accepted) < maximum
        result.append(allow)
        if allow:
            accepted.append(now)
    return result
