"""Original interview practice for 17-infrastructure-and-production/18-vllm-production-stack-lmcache.

Local source: phases/17-infrastructure-and-production/18-vllm-production-stack-lmcache/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def lru_keys(accesses, capacity):
    """Replay string-key accesses in a cache of exact nonnegative integer capacity. Every access inserts/touches the key. Evict least recently used when full. Return final keys from least to most recent. capacity 0 returns []; invalid capacity raises ValueError."""
    raise NotImplementedError('TODO 1: lru_keys; see PROMPT.md')

def make_batches(items, maximum):
    """items are {'id','tokens':exact positive int}; maximum exact positive int. Preserve input order, greedily pack consecutive items while sum tokens<=maximum. Oversized item raises ValueError rather than silently dropping it. Return list of lists of ids; empty input yields []."""
    raise NotImplementedError('TODO 2: make_batches; see PROMPT.md')
