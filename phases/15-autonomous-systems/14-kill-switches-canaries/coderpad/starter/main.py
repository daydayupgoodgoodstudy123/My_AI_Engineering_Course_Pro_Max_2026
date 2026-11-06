"""Original interview practice for 15-autonomous-systems/14-kill-switches-canaries.

Local source: phases/15-autonomous-systems/14-kill-switches-canaries/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def canary_decision(samples, max_error_rate, max_p95):
    """Each sample has ok exact bool and latency>=0. Empty samples returns 'insufficient'. Validate thresholds 0<=max_error_rate<=1,max_p95>=0 and samples; invalid input raises ValueError. Compute nearest-rank p95. Return 'rollback' if error rate>threshold or p95>threshold; otherwise 'promote'. These are local decisions, no deployment."""
    raise NotImplementedError('TODO 1: canary_decision; see PROMPT.md')

def evidence_gate(evidence, required):
    """For each sorted unique required name, accept only evidence[name] is exactly True. Return {'ready':bool,'failed':sorted names}. Missing, false, None and truthy non-bool values all fail. Unrequired evidence does not affect readiness. No deployment is performed."""
    raise NotImplementedError('TODO 2: evidence_gate; see PROMPT.md')
