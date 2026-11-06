"""Original interview practice for 20-recursive-self-improvement/07-zero-data-self-play-reasoning.

Local source: phases/20-recursive-self-improvement/07-zero-data-self-play-reasoning/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def inverse_cdf(probabilities, uniforms):
    """Probabilities must be nonempty, nonnegative, sum to 1 within 1e-9. Each uniform is in [0,1). Return the first index whose cumulative probability is strictly greater than u. Invalid input raises ValueError; empty uniforms returns []. No RNG is called."""
    raise NotImplementedError('TODO 1: inverse_cdf; see PROMPT.md')

def evidence_gate(evidence, required):
    """For each sorted unique required name, accept only evidence[name] is exactly True. Return {'ready':bool,'failed':sorted names}. Missing, false, None and truthy non-bool values all fail. Unrequired evidence does not affect readiness. No deployment is performed."""
    raise NotImplementedError('TODO 2: evidence_gate; see PROMPT.md')
