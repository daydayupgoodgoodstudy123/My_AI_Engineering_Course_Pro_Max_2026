"""Original interview practice for 14-agent-engineering/24-agent-observability-platforms.

Local source: phases/14-agent-engineering/24-agent-observability-platforms/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def latency_report(latencies, deadline):
    if not latencies or any((t < 0 for t in latencies)) or deadline < 0:
        raise ValueError('latency')
    ordered = sorted(latencies)
    n = len(ordered)
    return {'p50': ordered[math.ceil(0.5 * n) - 1], 'p95': ordered[math.ceil(0.95 * n) - 1], 'goodput_fraction': sum((t <= deadline for t in latencies)) / n}

def token_cost(usage, prices):
    totals = {}
    for r in usage:
        pin, pout = prices[r['provider']]
        if pin < 0 or pout < 0 or any((type(r[k]) is not int or r[k] < 0 for k in ('input_tokens', 'output_tokens'))):
            raise ValueError('usage')
        totals[r['provider']] = totals.get(r['provider'], 0) + r['input_tokens'] * pin + r['output_tokens'] * pout
    return {'total': sum(totals.values()), 'by_provider': totals}
