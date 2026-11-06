"""Original interview practice for 17-infrastructure-and-production/19-ai-gateways.

Local source: phases/17-infrastructure-and-production/19-ai-gateways/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import deque

def permission_decision(capability, granted, side_effect, approved):
    if type(side_effect) is not bool or type(approved) is not bool:
        raise ValueError('flags')
    if capability not in granted:
        return 'deny'
    return 'ask' if side_effect and (not approved) else 'allow'

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
