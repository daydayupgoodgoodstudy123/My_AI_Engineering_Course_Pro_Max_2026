"""Original interview practice for 10-llms-from-scratch/07-rlhf.

Local source: phases/10-llms-from-scratch/07-rlhf/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def advantages(rewards, values, gamma):
    if len(values) != len(rewards) + 1 or not 0 <= gamma <= 1:
        raise ValueError('trajectory')
    return [r + gamma * values[i + 1] - values[i] for i, r in enumerate(rewards)]

def discounted_returns(rewards, gamma):
    if not 0 <= gamma <= 1:
        raise ValueError('gamma')
    result = []
    running = 0
    for reward in reversed(rewards):
        running = reward + gamma * running
        result.append(running)
    return list(reversed(result))
