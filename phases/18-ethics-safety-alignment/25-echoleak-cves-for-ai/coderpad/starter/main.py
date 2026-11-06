"""Original interview practice for 18-ethics-safety-alignment/25-echoleak-cves-for-ai.

Local source: phases/18-ethics-safety-alignment/25-echoleak-cves-for-ai/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def permission_decision(capability, granted, side_effect, approved):
    """If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes."""
    raise NotImplementedError('TODO 1: permission_decision; see PROMPT.md')

def redact(value):
    """Recursively copy JSON values; replace the entire value of any dict key whose casefolded spelling is token,password,api_key,authorization with '[REDACTED]'. Other scalar values stay unchanged. This key-based policy does not discover secrets embedded in free text."""
    raise NotImplementedError('TODO 2: redact; see PROMPT.md')
