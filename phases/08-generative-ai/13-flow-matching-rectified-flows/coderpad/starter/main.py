"""Original interview practice for 08-generative-ai/13-flow-matching-rectified-flows.

Local source: phases/08-generative-ai/13-flow-matching-rectified-flows/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def flow_step(state, velocity, delta):
    """Return state+delta*velocity coordinatewise. Require equal lengths and numeric delta in [0,1]; otherwise ValueError. Empty vectors are valid."""
    raise NotImplementedError('TODO 1: flow_step; see PROMPT.md')

def gradient_step(weights, gradients, rate):
    """Return w-rate*g for equal-length numeric vectors and rate>=0. Unequal lengths or negative rate raises ValueError. Preserve inputs; empty vectors are valid."""
    raise NotImplementedError('TODO 2: gradient_step; see PROMPT.md')
