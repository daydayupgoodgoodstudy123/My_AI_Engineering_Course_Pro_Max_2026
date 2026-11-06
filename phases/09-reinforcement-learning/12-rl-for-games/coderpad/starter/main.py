"""Original interview practice for 09-reinforcement-learning/12-rl-for-games.

Local source: phases/09-reinforcement-learning/12-rl-for-games/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def bellman_backup(actions, gamma):
    """Each action is a nonempty list of [probability,reward,next_value] transitions. Probabilities per action must be nonnegative and sum to 1 within 1e-9. Return max over actions of sum(p*(r+gamma*v)). Require at least one action and gamma in [0,1], else ValueError."""
    raise NotImplementedError('TODO 1: bellman_backup; see PROMPT.md')

def select_ucb(means, visits, total, exploration):
    """means/visits must be same-length nonempty lists; visits are exact nonnegative ints; total exact int >=1, exploration>=0. Return first unvisited index if any; else maximize mean+c*sqrt(log(total)/visits), ties lower index. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 2: select_ucb; see PROMPT.md')
