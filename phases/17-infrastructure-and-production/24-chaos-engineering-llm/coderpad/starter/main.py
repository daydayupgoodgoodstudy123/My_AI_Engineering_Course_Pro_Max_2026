"""Original interview practice for 17-infrastructure-and-production/24-chaos-engineering-llm.

Local source: phases/17-infrastructure-and-production/24-chaos-engineering-llm/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def retry_delays(attempts, base, cap):
    """Return [min(cap,base*2**i) for i in range(attempts)]. attempts exact int 0..30; base/cap nonnegative numeric. Invalid input raises ValueError. No sleeping, randomness or calls are performed."""
    raise NotImplementedError('TODO 1: retry_delays; see PROMPT.md')

def evidence_gate(evidence, required):
    """For each sorted unique required name, accept only evidence[name] is exactly True. Return {'ready':bool,'failed':sorted names}. Missing, false, None and truthy non-bool values all fail. Unrequired evidence does not affect readiness. No deployment is performed."""
    raise NotImplementedError('TODO 2: evidence_gate; see PROMPT.md')
