"""Original interview practice for 09-reinforcement-learning/07-actor-critic-a2c-a3c.

Local source: phases/09-reinforcement-learning/07-actor-critic-a2c-a3c/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def advantages(rewards, values, gamma):
    if len(values) != len(rewards) + 1 or not 0 <= gamma <= 1:
        raise ValueError('trajectory')
    return [r + gamma * values[i + 1] - values[i] for i, r in enumerate(rewards)]

def gradient_step(weights, gradients, rate):
    if len(weights) != len(gradients) or rate < 0:
        raise ValueError('contract')
    return [w - rate * g for w, g in zip(weights, gradients)]
