"""Original interview practice for 09-reinforcement-learning/12-rl-for-games.

Local source: phases/09-reinforcement-learning/12-rl-for-games/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def bellman_backup(actions, gamma):
    if not actions or not 0 <= gamma <= 1 or any((not a or any((t[0] < 0 for t in a)) or abs(sum((t[0] for t in a)) - 1) > 1e-09 for a in actions)):
        raise ValueError('MDP')
    return max((sum((p * (r + gamma * v) for p, r, v in action)) for action in actions))

def select_ucb(means, visits, total, exploration):
    if not means or len(means) != len(visits) or type(total) is not int or (total < 1) or (exploration < 0) or any((type(v) is not int or v < 0 for v in visits)):
        raise ValueError('UCB')
    if 0 in visits:
        return visits.index(0)
    return max(range(len(means)), key=lambda i: means[i] + exploration * math.sqrt(math.log(total) / visits[i]))
