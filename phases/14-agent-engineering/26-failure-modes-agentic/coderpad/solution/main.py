"""Original interview practice for 14-agent-engineering/26-failure-modes-agentic.

Local source: phases/14-agent-engineering/26-failure-modes-agentic/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def retry_delays(attempts, base, cap):
    if type(attempts) is not int or not 0 <= attempts <= 30 or base < 0 or (cap < 0):
        raise ValueError('retry')
    return [min(cap, base * 2 ** i) for i in range(attempts)]

def transition(state, target):
    edges = {'queued': {'running', 'canceled'}, 'running': {'waiting', 'completed', 'failed', 'canceled'}, 'waiting': {'running', 'canceled'}}
    if target not in edges.get(state, set()):
        raise ValueError('transition')
    return target
