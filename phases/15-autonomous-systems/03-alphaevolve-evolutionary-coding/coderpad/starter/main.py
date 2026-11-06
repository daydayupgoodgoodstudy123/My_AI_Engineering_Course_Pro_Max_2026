"""Original interview practice for 15-autonomous-systems/03-alphaevolve-evolutionary-coding.

Local source: phases/15-autonomous-systems/03-alphaevolve-evolutionary-coding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def pareto_front(candidates):
    """Candidates have unique id strings, quality higher-is-better, cost lower-is-better. Return sorted ids not dominated by another candidate that is no worse in both and strictly better in at least one. Equal quality/cost entries both survive; empty input yields []."""
    raise NotImplementedError('TODO 1: pareto_front; see PROMPT.md')

def evidence_gate(evidence, required):
    """For each sorted unique required name, accept only evidence[name] is exactly True. Return {'ready':bool,'failed':sorted names}. Missing, false, None and truthy non-bool values all fail. Unrequired evidence does not affect readiness. No deployment is performed."""
    raise NotImplementedError('TODO 2: evidence_gate; see PROMPT.md')
