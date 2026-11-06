"""Original interview practice for 09-reinforcement-learning/03-monte-carlo-methods.

Local source: phases/09-reinforcement-learning/03-monte-carlo-methods/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def discounted_returns(rewards, gamma):
    if not 0 <= gamma <= 1:
        raise ValueError('gamma')
    result = []
    running = 0
    for reward in reversed(rewards):
        running = reward + gamma * running
        result.append(running)
    return list(reversed(result))

def summary(values):
    if not values:
        raise ValueError('empty')
    mean = sum(values) / len(values)
    return {'mean': mean, 'variance': sum(((x - mean) ** 2 for x in values)) / len(values), 'min': min(values), 'max': max(values)}
