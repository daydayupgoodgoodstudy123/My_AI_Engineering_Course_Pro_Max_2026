"""Original interview practice for 03-deep-learning-core/06-optimizers.

Local source: phases/03-deep-learning-core/06-optimizers/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def gradient_step(weights, gradients, rate):
    """Return w-rate*g for equal-length numeric vectors and rate>=0. Unequal lengths or negative rate raises ValueError. Preserve inputs; empty vectors are valid."""
    raise NotImplementedError('TODO 1: gradient_step; see PROMPT.md')

def clip_gradients(gradients, maximum):
    """Return gradients scaled together so L2 norm is at most maximum; leave already-small vectors unchanged in value. maximum>=0, otherwise ValueError. Zero and empty vectors are valid."""
    raise NotImplementedError('TODO 2: clip_gradients; see PROMPT.md')
