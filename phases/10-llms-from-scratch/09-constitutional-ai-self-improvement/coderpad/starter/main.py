"""Original interview practice for 10-llms-from-scratch/09-constitutional-ai-self-improvement.

Local source: phases/10-llms-from-scratch/09-constitutional-ai-self-improvement/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def moderation(signals, block_at):
    """Each signal has category(str), severity exact int 0..3. block_at exact int 0..3. Keep max severity per category, return {'categories':sorted category->max mapping,'blocked':any severity>=block_at}. Empty signals never block. Invalid severity/threshold raises ValueError. No model classifier is called."""
    raise NotImplementedError('TODO 1: moderation; see PROMPT.md')

def evidence_gate(evidence, required):
    """For each sorted unique required name, accept only evidence[name] is exactly True. Return {'ready':bool,'failed':sorted names}. Missing, false, None and truthy non-bool values all fail. Unrequired evidence does not affect readiness. No deployment is performed."""
    raise NotImplementedError('TODO 2: evidence_gate; see PROMPT.md')
