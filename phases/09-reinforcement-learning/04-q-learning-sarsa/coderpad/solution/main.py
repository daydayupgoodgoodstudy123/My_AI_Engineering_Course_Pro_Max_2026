"""Original interview practice for 09-reinforcement-learning/04-q-learning-sarsa.

Local source: phases/09-reinforcement-learning/04-q-learning-sarsa/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def q_update(current, reward, next_values, alpha, gamma, terminal=False):
    if not 0 <= alpha <= 1 or not 0 <= gamma <= 1 or (not terminal and (not next_values)):
        raise ValueError('transition')
    target = reward + (0 if terminal else gamma * max(next_values))
    return current + alpha * (target - current)

def discounted_returns(rewards, gamma):
    if not 0 <= gamma <= 1:
        raise ValueError('gamma')
    result = []
    running = 0
    for reward in reversed(rewards):
        running = reward + gamma * running
        result.append(running)
    return list(reversed(result))
