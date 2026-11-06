"""Original interview practice for 17-infrastructure-and-production/22-load-testing-llm-apis.

Local source: phases/17-infrastructure-and-production/22-load-testing-llm-apis/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import deque

def rate_limit(times, window, maximum):
    """Times are nondecreasing numeric timestamps. Keep only accepted timestamps in (now-window,now]. Accept when fewer than maximum remain. maximum exact positive int and window>0; descending timestamps/invalid config raises ValueError. Return decision bools; rejected events consume no slot."""
    raise NotImplementedError('TODO 1: rate_limit; see PROMPT.md')

def latency_report(latencies, deadline):
    """Use nonempty nonnegative numeric latencies and deadline>=0. Return {'p50':nearest-rank median,'p95':nearest-rank 95th percentile,'goodput_fraction':fraction <=deadline}. Nearest-rank index=ceil(p*n)-1. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 2: latency_report; see PROMPT.md')
