"""Original interview practice for 09-reinforcement-learning/07-actor-critic-a2c-a3c.

Local source: phases/09-reinforcement-learning/07-actor-critic-a2c-a3c/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def advantages(rewards, values, gamma):
    """values contains one more element than rewards. Return one-step TD advantage r[t]+gamma*v[t+1]-v[t]. Require gamma in [0,1] and exact length relation; otherwise ValueError. Empty rewards plus one value returns []."""
    raise NotImplementedError('TODO 1: advantages; see PROMPT.md')

def gradient_step(weights, gradients, rate):
    """Return w-rate*g for equal-length numeric vectors and rate>=0. Unequal lengths or negative rate raises ValueError. Preserve inputs; empty vectors are valid."""
    raise NotImplementedError('TODO 2: gradient_step; see PROMPT.md')
