"""Original interview practice for 09-reinforcement-learning/05-dqn.

Local source: phases/09-reinforcement-learning/05-dqn/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def q_update(current, reward, next_values, alpha, gamma, terminal=False):
    if not 0 <= alpha <= 1 or not 0 <= gamma <= 1 or (not terminal and (not next_values)):
        raise ValueError('transition')
    target = reward + (0 if terminal else gamma * max(next_values))
    return current + alpha * (target - current)

def clip_gradients(gradients, maximum):
    if maximum < 0:
        raise ValueError('maximum')
    norm = math.sqrt(sum((g * g for g in gradients)))
    scale = min(1, maximum / norm) if norm else 1
    return [g * scale for g in gradients]
