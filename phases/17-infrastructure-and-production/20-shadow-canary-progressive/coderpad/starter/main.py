"""Original interview practice for 17-infrastructure-and-production/20-shadow-canary-progressive.

Local source: phases/17-infrastructure-and-production/20-shadow-canary-progressive/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def canary_decision(samples, max_error_rate, max_p95):
    """Each sample has ok exact bool and latency>=0. Empty samples returns 'insufficient'. Validate thresholds 0<=max_error_rate<=1,max_p95>=0 and samples; invalid input raises ValueError. Compute nearest-rank p95. Return 'rollback' if error rate>threshold or p95>threshold; otherwise 'promote'. These are local decisions, no deployment."""
    raise NotImplementedError('TODO 1: canary_decision; see PROMPT.md')

def latency_report(latencies, deadline):
    """Use nonempty nonnegative numeric latencies and deadline>=0. Return {'p50':nearest-rank median,'p95':nearest-rank 95th percentile,'goodput_fraction':fraction <=deadline}. Nearest-rank index=ceil(p*n)-1. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 2: latency_report; see PROMPT.md')
