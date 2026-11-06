"""Original interview practice for 09-reinforcement-learning/03-monte-carlo-methods.

Local source: phases/09-reinforcement-learning/03-monte-carlo-methods/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def discounted_returns(rewards, gamma):
    """Return G[t]=rewards[t]+gamma*G[t+1], final continuation 0. gamma must be in [0,1], otherwise ValueError. Empty rewards returns []."""
    raise NotImplementedError('TODO 1: discounted_returns; see PROMPT.md')

def summary(values):
    """Return {'mean':arithmetic mean,'variance':population variance,'min':minimum,'max':maximum} for a nonempty numeric list. Empty input raises ValueError."""
    raise NotImplementedError('TODO 2: summary; see PROMPT.md')
