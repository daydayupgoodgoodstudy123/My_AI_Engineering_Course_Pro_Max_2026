"""Original interview practice for 12-multimodal-ai/04-flamingo-gated-cross-attention.

Local source: phases/12-multimodal-ai/04-flamingo-gated-cross-attention/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def attention(query, keys, values):
    """query is nonempty length d; keys is nonempty NxD and values is NxV with nonempty equal row widths. Compute softmax(query dot key / sqrt(d)) then the weighted sum of value rows. Invalid shapes raise ValueError; implement with Python lists."""
    raise NotImplementedError('TODO 1: attention; see PROMPT.md')

def flow_step(state, velocity, delta):
    """Return state+delta*velocity coordinatewise. Require equal lengths and numeric delta in [0,1]; otherwise ValueError. Empty vectors are valid."""
    raise NotImplementedError('TODO 2: flow_step; see PROMPT.md')
