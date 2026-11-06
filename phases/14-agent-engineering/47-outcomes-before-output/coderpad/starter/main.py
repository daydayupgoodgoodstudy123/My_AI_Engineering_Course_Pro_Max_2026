"""Original interview practice for 14-agent-engineering/47-outcomes-before-output.

Local source: phases/14-agent-engineering/47-outcomes-before-output/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def evidence_gate(evidence, required):
    """For each sorted unique required name, accept only evidence[name] is exactly True. Return {'ready':bool,'failed':sorted names}. Missing, false, None and truthy non-bool values all fail. Unrequired evidence does not affect readiness. No deployment is performed."""
    raise NotImplementedError('TODO 1: evidence_gate; see PROMPT.md')

def profile(events):
    """Events have name,start,end numeric milliseconds. Reject end<start with ValueError. Return name->{'count','total','max'} aggregated over individual durations. Empty input -> {}; overlapping durations are summed, not wall-clock latency."""
    raise NotImplementedError('TODO 2: profile; see PROMPT.md')
