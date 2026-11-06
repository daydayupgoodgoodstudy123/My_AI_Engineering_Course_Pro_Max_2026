"""Original interview practice for 19-capstone-projects/34-transformer-block.

Local source: phases/19-capstone-projects/34-transformer-block/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def layer_norm(values, epsilon=1e-05):
    """For a nonempty vector compute (x-mean)/sqrt(population_variance+epsilon). epsilon must be >0. Invalid inputs raise ValueError; return a new list."""
    raise NotImplementedError('TODO 1: layer_norm; see PROMPT.md')

def activation(values, kind='relu', slope=0.01):
    """Map numeric values through relu, leaky_relu, or tanh. relu=max(0,x); leaky_relu uses slope*x only for x<0. Unknown kind or negative slope raises ValueError; empty input returns []."""
    raise NotImplementedError('TODO 2: activation; see PROMPT.md')
