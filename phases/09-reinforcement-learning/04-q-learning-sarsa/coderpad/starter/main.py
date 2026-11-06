"""Original interview practice for 09-reinforcement-learning/04-q-learning-sarsa.

Local source: phases/09-reinforcement-learning/04-q-learning-sarsa/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def q_update(current, reward, next_values, alpha, gamma, terminal=False):
    """Require alpha,gamma in [0,1]. For terminal transition target=reward and next_values may be empty; otherwise require nonempty next_values and target=reward+gamma*max(next_values). Return current+alpha*(target-current). Invalid inputs raise ValueError."""
    raise NotImplementedError('TODO 1: q_update; see PROMPT.md')

def discounted_returns(rewards, gamma):
    """Return G[t]=rewards[t]+gamma*G[t+1], final continuation 0. gamma must be in [0,1], otherwise ValueError. Empty rewards returns []."""
    raise NotImplementedError('TODO 2: discounted_returns; see PROMPT.md')
