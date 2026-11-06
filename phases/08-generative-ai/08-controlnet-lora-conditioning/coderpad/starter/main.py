"""Original interview practice for 08-generative-ai/08-controlnet-lora-conditioning.

Local source: phases/08-generative-ai/08-controlnet-lora-conditioning/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def lora_delta(a, b, alpha):
    """A is nonempty output-by-rank, B is rank-by-input, both rectangular with nonempty rows. Return (alpha/rank)*A@B; alpha is finite numeric. Invalid shapes raise ValueError. No base weights are modified."""
    raise NotImplementedError('TODO 1: lora_delta; see PROMPT.md')

def flow_step(state, velocity, delta):
    """Return state+delta*velocity coordinatewise. Require equal lengths and numeric delta in [0,1]; otherwise ValueError. Empty vectors are valid."""
    raise NotImplementedError('TODO 2: flow_step; see PROMPT.md')
