"""Original interview practice for 17-infrastructure-and-production/05-eagle3-speculative-decoding.

Local source: phases/17-infrastructure-and-production/05-eagle3-speculative-decoding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def accept_prefix(draft, verified):
    i = 0
    while i < min(len(draft), len(verified)) and draft[i] == verified[i]:
        i += 1
    return {'accepted': draft[:i], 'next': verified[i] if i < len(verified) else None}

def latency_report(latencies, deadline):
    if not latencies or any((t < 0 for t in latencies)) or deadline < 0:
        raise ValueError('latency')
    ordered = sorted(latencies)
    n = len(ordered)
    return {'p50': ordered[math.ceil(0.5 * n) - 1], 'p95': ordered[math.ceil(0.95 * n) - 1], 'goodput_fraction': sum((t <= deadline for t in latencies)) / n}
