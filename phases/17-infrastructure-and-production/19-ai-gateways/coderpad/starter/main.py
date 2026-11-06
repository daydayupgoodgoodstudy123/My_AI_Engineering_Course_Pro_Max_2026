"""Original interview practice for 17-infrastructure-and-production/19-ai-gateways.

Local source: phases/17-infrastructure-and-production/19-ai-gateways/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import deque

def permission_decision(capability, granted, side_effect, approved):
    """If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes."""
    raise NotImplementedError('TODO 1: permission_decision; see PROMPT.md')

def rate_limit(times, window, maximum):
    """Times are nondecreasing numeric timestamps. Keep only accepted timestamps in (now-window,now]. Accept when fewer than maximum remain. maximum exact positive int and window>0; descending timestamps/invalid config raises ValueError. Return decision bools; rejected events consume no slot."""
    raise NotImplementedError('TODO 2: rate_limit; see PROMPT.md')
