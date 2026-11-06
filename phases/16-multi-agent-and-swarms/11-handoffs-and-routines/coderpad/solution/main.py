"""Original interview practice for 16-multi-agent-and-swarms/11-handoffs-and-routines.

Local source: phases/16-multi-agent-and-swarms/11-handoffs-and-routines/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def validate_handoff(bundle):
    issues = [k for k in ('objective', 'state', 'next_action') if not isinstance(bundle.get(k), str) or not bundle[k].strip()]
    checks = bundle.get('checks')
    if not isinstance(checks, list) or not checks or any((not isinstance(x, str) or not x.strip() for x in checks)):
        issues.append('checks')
    return sorted(issues)

def transition(state, target):
    edges = {'queued': {'running', 'canceled'}, 'running': {'waiting', 'completed', 'failed', 'canceled'}, 'waiting': {'running', 'canceled'}}
    if target not in edges.get(state, set()):
        raise ValueError('transition')
    return target
