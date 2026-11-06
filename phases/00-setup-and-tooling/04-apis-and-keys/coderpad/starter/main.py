"""Original interview practice for 00-setup-and-tooling/04-apis-and-keys.

Local source: phases/00-setup-and-tooling/04-apis-and-keys/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def validate_config(config, required, optional):
    """required and optional are field-name lists. Return {'missing':sorted required absent keys,'unknown':sorted config keys outside required+optional,'valid':no findings}. Values are deliberately not type-checked here. Empty config can be valid."""
    raise NotImplementedError('TODO 1: validate_config; see PROMPT.md')

def redact(value):
    """Recursively copy JSON values; replace the entire value of any dict key whose casefolded spelling is token,password,api_key,authorization with '[REDACTED]'. Other scalar values stay unchanged. This key-based policy does not discover secrets embedded in free text."""
    raise NotImplementedError('TODO 2: redact; see PROMPT.md')
