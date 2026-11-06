"""Original interview practice for 14-agent-engineering/26-failure-modes-agentic.

Local source: phases/14-agent-engineering/26-failure-modes-agentic/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def retry_delays(attempts, base, cap):
    """Return [min(cap,base*2**i) for i in range(attempts)]. attempts exact int 0..30; base/cap nonnegative numeric. Invalid input raises ValueError. No sleeping, randomness or calls are performed."""
    raise NotImplementedError('TODO 1: retry_delays; see PROMPT.md')

def transition(state, target):
    """Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves."""
    raise NotImplementedError('TODO 2: transition; see PROMPT.md')
