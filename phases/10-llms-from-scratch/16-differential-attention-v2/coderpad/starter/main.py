"""Original interview practice for 10-llms-from-scratch/16-differential-attention-v2.

Local source: phases/10-llms-from-scratch/16-differential-attention-v2/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def attention(query, keys, values):
    """query is nonempty length d; keys is nonempty NxD and values is NxV with nonempty equal row widths. Compute softmax(query dot key / sqrt(d)) then the weighted sum of value rows. Invalid shapes raise ValueError; implement with Python lists."""
    raise NotImplementedError('TODO 1: attention; see PROMPT.md')

def layer_norm(values, epsilon=1e-05):
    """For a nonempty vector compute (x-mean)/sqrt(population_variance+epsilon). epsilon must be >0. Invalid inputs raise ValueError; return a new list."""
    raise NotImplementedError('TODO 2: layer_norm; see PROMPT.md')
