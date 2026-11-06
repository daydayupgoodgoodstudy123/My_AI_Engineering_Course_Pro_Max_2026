"""Original interview practice for 09-reinforcement-learning/08-ppo.

Local source: phases/09-reinforcement-learning/08-ppo/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def ppo_objective(ratios, advantages, epsilon):
    if not ratios or len(ratios) != len(advantages) or any((r < 0 for r in ratios)) or (not 0 <= epsilon < 1):
        raise ValueError('PPO')
    return sum((min(r * a, max(1 - epsilon, min(1 + epsilon, r)) * a) for r, a in zip(ratios, advantages))) / len(ratios)

def advantages(rewards, values, gamma):
    if len(values) != len(rewards) + 1 or not 0 <= gamma <= 1:
        raise ValueError('trajectory')
    return [r + gamma * values[i + 1] - values[i] for i, r in enumerate(rewards)]
