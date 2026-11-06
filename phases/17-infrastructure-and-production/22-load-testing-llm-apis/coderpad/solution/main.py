"""Original interview practice for 17-infrastructure-and-production/22-load-testing-llm-apis.

Local source: phases/17-infrastructure-and-production/22-load-testing-llm-apis/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import deque

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

def latency_report(latencies, deadline):
    if not latencies or any((t < 0 for t in latencies)) or deadline < 0:
        raise ValueError('latency')
    ordered = sorted(latencies)
    n = len(ordered)
    return {'p50': ordered[math.ceil(0.5 * n) - 1], 'p95': ordered[math.ceil(0.95 * n) - 1], 'goodput_fraction': sum((t <= deadline for t in latencies)) / n}
