"""Original interview practice for 09-reinforcement-learning/01-mdps-states-actions-rewards.

Local source: phases/09-reinforcement-learning/01-mdps-states-actions-rewards/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bellman_backup(actions, gamma):
    if not actions or not 0 <= gamma <= 1 or any((not a or any((t[0] < 0 for t in a)) or abs(sum((t[0] for t in a)) - 1) > 1e-09 for a in actions)):
        raise ValueError('MDP')
    return max((sum((p * (r + gamma * v) for p, r, v in action)) for action in actions))

def markov_step(distribution, transition):
    n = len(distribution)
    if not n or len(transition) != n or any((len(r) != n for r in transition)) or any((p < 0 for r in [distribution] + transition for p in r)) or any((abs(sum(r) - 1) > 1e-09 for r in [distribution] + transition)):
        raise ValueError('stochastic matrix')
    return [sum((distribution[i] * transition[i][j] for i in range(n))) for j in range(n)]
