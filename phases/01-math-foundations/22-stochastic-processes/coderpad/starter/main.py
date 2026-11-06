"""Original interview practice for 01-math-foundations/22-stochastic-processes.

Local source: phases/01-math-foundations/22-stochastic-processes/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def markov_step(distribution, transition):
    """Distribution is a nonempty probability row vector; transition is an NxN row-stochastic matrix. Reject wrong shapes, negatives or row/distribution sums outside 1e-9 with ValueError. Return distribution @ transition."""
    raise NotImplementedError('TODO 1: markov_step; see PROMPT.md')

def discounted_returns(rewards, gamma):
    """Return G[t]=rewards[t]+gamma*G[t+1], final continuation 0. gamma must be in [0,1], otherwise ValueError. Empty rewards returns []."""
    raise NotImplementedError('TODO 2: discounted_returns; see PROMPT.md')
