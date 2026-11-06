"""Original interview practice for 15-autonomous-systems/09-coding-agent-landscape.

Local source: phases/15-autonomous-systems/09-coding-agent-landscape/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def route_task(routes, query_tokens, role):
    if len({r['name'] for r in routes}) != len(routes):
        raise ValueError('duplicate route')
    scores = [(len(set(r['keywords']) & set(query_tokens)), r['name']) for r in routes if role in r['roles']]
    best = max((s for s, n in scores), default=0)
    names = [n for s, n in scores if s == best]
    return names[0] if best > 0 and len(names) == 1 else None

def validate_config(config, required, optional):
    missing = sorted(set(required) - set(config))
    unknown = sorted(set(config) - set(required) - set(optional))
    return {'missing': missing, 'unknown': unknown, 'valid': not missing and (not unknown)}
