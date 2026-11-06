"""Original interview practice for 17-infrastructure-and-production/20-shadow-canary-progressive.

Local source: phases/17-infrastructure-and-production/20-shadow-canary-progressive/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def canary_decision(samples, max_error_rate, max_p95):
    if not 0 <= max_error_rate <= 1 or max_p95 < 0 or any((type(s['ok']) is not bool or s['latency'] < 0 for s in samples)):
        raise ValueError('evidence')
    if not samples:
        return 'insufficient'
    rate = sum((not s['ok'] for s in samples)) / len(samples)
    p95 = sorted((s['latency'] for s in samples))[math.ceil(0.95 * len(samples)) - 1]
    return 'rollback' if rate > max_error_rate or p95 > max_p95 else 'promote'

def latency_report(latencies, deadline):
    if not latencies or any((t < 0 for t in latencies)) or deadline < 0:
        raise ValueError('latency')
    ordered = sorted(latencies)
    n = len(ordered)
    return {'p50': ordered[math.ceil(0.5 * n) - 1], 'p95': ordered[math.ceil(0.95 * n) - 1], 'goodput_fraction': sum((t <= deadline for t in latencies)) / n}
