"""Original interview practice for 19-capstone-projects/44-cosine-lr-warmup.

Local source: phases/19-capstone-projects/44-cosine-lr-warmup/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def learning_rate(step, total, warmup, peak):
    """Require exact integer total>0, 0<=warmup<total, step>=0, and peak>=0. If step<warmup return peak*step/warmup; otherwise peak*(1+cos(pi*min(1,(step-warmup)/(total-warmup))))/2. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: learning_rate; see PROMPT.md')

def clip_gradients(gradients, maximum):
    """Return gradients scaled together so L2 norm is at most maximum; leave already-small vectors unchanged in value. maximum>=0, otherwise ValueError. Zero and empty vectors are valid."""
    raise NotImplementedError('TODO 2: clip_gradients; see PROMPT.md')
