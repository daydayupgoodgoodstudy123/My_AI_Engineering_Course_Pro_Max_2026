"""Original interview practice for 20-recursive-self-improvement/04-self-play-closed-loops.

Local source: phases/20-recursive-self-improvement/04-self-play-closed-loops/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bellman_backup(actions, gamma):
    """Each action is a nonempty list of [probability,reward,next_value] transitions. Probabilities per action must be nonnegative and sum to 1 within 1e-9. Return max over actions of sum(p*(r+gamma*v)). Require at least one action and gamma in [0,1], else ValueError."""
    raise NotImplementedError('TODO 1: bellman_backup; see PROMPT.md')

def discounted_returns(rewards, gamma):
    """Return G[t]=rewards[t]+gamma*G[t+1], final continuation 0. gamma must be in [0,1], otherwise ValueError. Empty rewards returns []."""
    raise NotImplementedError('TODO 2: discounted_returns; see PROMPT.md')
