"""Original interview practice for 14-agent-engineering/53-prototype-pilot-or-production.

Local source: phases/14-agent-engineering/53-prototype-pilot-or-production/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def evidence_gate(evidence, required):
    failed = sorted((k for k in set(required) if evidence.get(k) is not True))
    return {'ready': not failed, 'failed': failed}

def unsupported_claims(claims, evidence_ids):
    if len({c['id'] for c in claims}) != len(claims):
        raise ValueError('duplicate claim')
    known = set(evidence_ids)
    return sorted((c['id'] for c in claims if not c['references'] or not set(c['references']) <= known))
