"""Original interview practice for 20-recursive-self-improvement/01-rsi-definitions-and-ladder.

Local source: phases/20-recursive-self-improvement/01-rsi-definitions-and-ladder/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def discounted_returns(rewards, gamma):
    """Return G[t]=rewards[t]+gamma*G[t+1], final continuation 0. gamma must be in [0,1], otherwise ValueError. Empty rewards returns []."""
    raise NotImplementedError('TODO 1: discounted_returns; see PROMPT.md')

def amdahl(serial_fraction, speedup):
    """Return 1/(serial_fraction+(1-serial_fraction)/speedup). Require serial_fraction in [0,1] and speedup>=1; otherwise ValueError. This models latency, not queueing throughput."""
    raise NotImplementedError('TODO 2: amdahl; see PROMPT.md')
