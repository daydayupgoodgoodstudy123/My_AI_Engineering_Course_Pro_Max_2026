"""Original interview practice for 20-recursive-self-improvement/01-rsi-definitions-and-ladder.

Local source: phases/20-recursive-self-improvement/01-rsi-definitions-and-ladder/docs/en.md (sha256 in SCOPE.json).
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

def amdahl(serial_fraction, speedup):
    if not 0 <= serial_fraction <= 1 or speedup < 1:
        raise ValueError('parameters')
    return 1 / (serial_fraction + (1 - serial_fraction) / speedup)
