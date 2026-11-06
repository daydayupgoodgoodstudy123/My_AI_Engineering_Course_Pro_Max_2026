"""Original interview practice for 15-autonomous-systems/14-kill-switches-canaries.

Local source: phases/15-autonomous-systems/14-kill-switches-canaries/docs/en.md (sha256 in SCOPE.json).
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

def evidence_gate(evidence, required):
    failed = sorted((k for k in set(required) if evidence.get(k) is not True))
    return {'ready': not failed, 'failed': failed}
