"""Original interview practice for 17-infrastructure-and-production/13-llm-observability.

Local source: phases/17-infrastructure-and-production/13-llm-observability/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def profile(events):
    """Events have name,start,end numeric milliseconds. Reject end<start with ValueError. Return name->{'count','total','max'} aggregated over individual durations. Empty input -> {}; overlapping durations are summed, not wall-clock latency."""
    raise NotImplementedError('TODO 1: profile; see PROMPT.md')

def redact(value):
    """Recursively copy JSON values; replace the entire value of any dict key whose casefolded spelling is token,password,api_key,authorization with '[REDACTED]'. Other scalar values stay unchanged. This key-based policy does not discover secrets embedded in free text."""
    raise NotImplementedError('TODO 2: redact; see PROMPT.md')
