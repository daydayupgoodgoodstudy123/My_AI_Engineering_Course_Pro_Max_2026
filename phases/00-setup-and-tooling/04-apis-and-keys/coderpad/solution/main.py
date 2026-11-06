"""Original interview practice for 00-setup-and-tooling/04-apis-and-keys.

Local source: phases/00-setup-and-tooling/04-apis-and-keys/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def validate_config(config, required, optional):
    missing = sorted(set(required) - set(config))
    unknown = sorted(set(config) - set(required) - set(optional))
    return {'missing': missing, 'unknown': unknown, 'valid': not missing and (not unknown)}

def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if k.casefold() in {'token', 'password', 'api_key', 'authorization'} else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value
