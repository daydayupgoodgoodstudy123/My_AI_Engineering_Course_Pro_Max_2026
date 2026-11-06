"""Original interview practice for 14-agent-engineering/20-benchmarks-webarena-osworld.

Local source: phases/14-agent-engineering/20-benchmarks-webarena-osworld/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def permission_decision(capability, granted, side_effect, approved):
    if type(side_effect) is not bool or type(approved) is not bool:
        raise ValueError('flags')
    if capability not in granted:
        return 'deny'
    return 'ask' if side_effect and (not approved) else 'allow'

def latency_report(latencies, deadline):
    if not latencies or any((t < 0 for t in latencies)) or deadline < 0:
        raise ValueError('latency')
    ordered = sorted(latencies)
    n = len(ordered)
    return {'p50': ordered[math.ceil(0.5 * n) - 1], 'p95': ordered[math.ceil(0.95 * n) - 1], 'goodput_fraction': sum((t <= deadline for t in latencies)) / n}
