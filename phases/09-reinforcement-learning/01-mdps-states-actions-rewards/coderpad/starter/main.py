"""Original interview practice for 09-reinforcement-learning/01-mdps-states-actions-rewards.

Local source: phases/09-reinforcement-learning/01-mdps-states-actions-rewards/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bellman_backup(actions, gamma):
    """Each action is a nonempty list of [probability,reward,next_value] transitions. Probabilities per action must be nonnegative and sum to 1 within 1e-9. Return max over actions of sum(p*(r+gamma*v)). Require at least one action and gamma in [0,1], else ValueError."""
    raise NotImplementedError('TODO 1: bellman_backup; see PROMPT.md')

def markov_step(distribution, transition):
    """Distribution is a nonempty probability row vector; transition is an NxN row-stochastic matrix. Reject wrong shapes, negatives or row/distribution sums outside 1e-9 with ValueError. Return distribution @ transition."""
    raise NotImplementedError('TODO 2: markov_step; see PROMPT.md')
