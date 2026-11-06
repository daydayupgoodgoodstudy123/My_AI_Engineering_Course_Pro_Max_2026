"""Original interview practice for 10-llms-from-scratch/07-rlhf.

Local source: phases/10-llms-from-scratch/07-rlhf/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def advantages(rewards, values, gamma):
    """values contains one more element than rewards. Return one-step TD advantage r[t]+gamma*v[t+1]-v[t]. Require gamma in [0,1] and exact length relation; otherwise ValueError. Empty rewards plus one value returns []."""
    raise NotImplementedError('TODO 1: advantages; see PROMPT.md')

def discounted_returns(rewards, gamma):
    """Return G[t]=rewards[t]+gamma*G[t+1], final continuation 0. gamma must be in [0,1], otherwise ValueError. Empty rewards returns []."""
    raise NotImplementedError('TODO 2: discounted_returns; see PROMPT.md')
