"""Original interview practice for 09-reinforcement-learning/02-dynamic-programming.

Local source: phases/09-reinforcement-learning/02-dynamic-programming/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bellman_backup(actions, gamma):
    if not actions or not 0 <= gamma <= 1 or any((not a or any((t[0] < 0 for t in a)) or abs(sum((t[0] for t in a)) - 1) > 1e-09 for a in actions)):
        raise ValueError('MDP')
    return max((sum((p * (r + gamma * v) for p, r, v in action)) for action in actions))

def discounted_returns(rewards, gamma):
    if not 0 <= gamma <= 1:
        raise ValueError('gamma')
    result = []
    running = 0
    for reward in reversed(rewards):
        running = reward + gamma * running
        result.append(running)
    return list(reversed(result))
