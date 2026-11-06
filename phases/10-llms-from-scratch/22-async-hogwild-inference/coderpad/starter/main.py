"""Original interview practice for 10-llms-from-scratch/22-async-hogwild-inference.

Local source: phases/10-llms-from-scratch/22-async-hogwild-inference/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
from collections import deque

def replay_requests(requests):
    """Requests have id and payload (JSON values). First use of id is executed and recorded; exact canonical-JSON payload replay is not executed again. Conflicting reuse raises ValueError. Return {'executed':[first-use ids], 'replayed':[duplicate ids in encounter order]}. Do not treat bool and int payloads as equal."""
    raise NotImplementedError('TODO 1: replay_requests; see PROMPT.md')

def rate_limit(times, window, maximum):
    """Times are nondecreasing numeric timestamps. Keep only accepted timestamps in (now-window,now]. Accept when fewer than maximum remain. maximum exact positive int and window>0; descending timestamps/invalid config raises ValueError. Return decision bools; rejected events consume no slot."""
    raise NotImplementedError('TODO 2: rate_limit; see PROMPT.md')
