"""Original interview practice for 09-reinforcement-learning/06-policy-gradients-reinforce.

Local source: phases/09-reinforcement-learning/06-policy-gradients-reinforce/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def discounted_returns(rewards, gamma):
    """Return G[t]=rewards[t]+gamma*G[t+1], final continuation 0. gamma must be in [0,1], otherwise ValueError. Empty rewards returns []."""
    raise NotImplementedError('TODO 1: discounted_returns; see PROMPT.md')

def softmax(values):
    """Return stable softmax probabilities for a nonempty list of finite logits, preserving order. Subtract the maximum before exponentiation. Empty input raises ValueError."""
    raise NotImplementedError('TODO 2: softmax; see PROMPT.md')
