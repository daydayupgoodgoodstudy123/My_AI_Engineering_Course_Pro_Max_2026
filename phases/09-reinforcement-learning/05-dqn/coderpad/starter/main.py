"""Original interview practice for 09-reinforcement-learning/05-dqn.

Local source: phases/09-reinforcement-learning/05-dqn/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def q_update(current, reward, next_values, alpha, gamma, terminal=False):
    """Require alpha,gamma in [0,1]. For terminal transition target=reward and next_values may be empty; otherwise require nonempty next_values and target=reward+gamma*max(next_values). Return current+alpha*(target-current). Invalid inputs raise ValueError."""
    raise NotImplementedError('TODO 1: q_update; see PROMPT.md')

def clip_gradients(gradients, maximum):
    """Return gradients scaled together so L2 norm is at most maximum; leave already-small vectors unchanged in value. maximum>=0, otherwise ValueError. Zero and empty vectors are valid."""
    raise NotImplementedError('TODO 2: clip_gradients; see PROMPT.md')
