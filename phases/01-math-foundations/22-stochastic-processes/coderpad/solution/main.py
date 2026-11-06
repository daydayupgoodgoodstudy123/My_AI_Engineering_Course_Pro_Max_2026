"""Original interview practice for 01-math-foundations/22-stochastic-processes.

Local source: phases/01-math-foundations/22-stochastic-processes/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def markov_step(distribution, transition):
    n = len(distribution)
    if not n or len(transition) != n or any((len(r) != n for r in transition)) or any((p < 0 for r in [distribution] + transition for p in r)) or any((abs(sum(r) - 1) > 1e-09 for r in [distribution] + transition)):
        raise ValueError('stochastic matrix')
    return [sum((distribution[i] * transition[i][j] for i in range(n))) for j in range(n)]

def discounted_returns(rewards, gamma):
    if not 0 <= gamma <= 1:
        raise ValueError('gamma')
    result = []
    running = 0
    for reward in reversed(rewards):
        running = reward + gamma * running
        result.append(running)
    return list(reversed(result))
