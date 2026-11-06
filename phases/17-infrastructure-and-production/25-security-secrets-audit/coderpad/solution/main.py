"""Original interview practice for 17-infrastructure-and-production/25-security-secrets-audit.

Local source: phases/17-infrastructure-and-production/25-security-secrets-audit/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if k.casefold() in {'token', 'password', 'api_key', 'authorization'} else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value

def permission_decision(capability, granted, side_effect, approved):
    if type(side_effect) is not bool or type(approved) is not bool:
        raise ValueError('flags')
    if capability not in granted:
        return 'deny'
    return 'ask' if side_effect and (not approved) else 'allow'
