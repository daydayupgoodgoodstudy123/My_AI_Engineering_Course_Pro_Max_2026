"""Original interview practice for 03-deep-learning-core/04-activation-functions.

Local source: phases/03-deep-learning-core/04-activation-functions/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def activation(values, kind='relu', slope=0.01):
    """Map numeric values through relu, leaky_relu, or tanh. relu=max(0,x); leaky_relu uses slope*x only for x<0. Unknown kind or negative slope raises ValueError; empty input returns []."""
    raise NotImplementedError('TODO 1: activation; see PROMPT.md')

def sigmoid(value):
    """Return logistic sigmoid for a finite scalar, avoiding overflow for large positive or negative magnitudes."""
    raise NotImplementedError('TODO 2: sigmoid; see PROMPT.md')
