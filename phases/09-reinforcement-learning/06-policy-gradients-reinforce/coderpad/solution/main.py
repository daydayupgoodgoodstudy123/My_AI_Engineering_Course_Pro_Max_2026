"""Original interview practice for 09-reinforcement-learning/06-policy-gradients-reinforce.

Local source: phases/09-reinforcement-learning/06-policy-gradients-reinforce/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def discounted_returns(rewards, gamma):
    if not 0 <= gamma <= 1:
        raise ValueError('gamma')
    result = []
    running = 0
    for reward in reversed(rewards):
        running = reward + gamma * running
        result.append(running)
    return list(reversed(result))

def softmax(values):
    if not values:
        raise ValueError('empty')
    maximum = max(values)
    weights = [math.exp(x - maximum) for x in values]
    total = sum(weights)
    return [x / total for x in weights]
