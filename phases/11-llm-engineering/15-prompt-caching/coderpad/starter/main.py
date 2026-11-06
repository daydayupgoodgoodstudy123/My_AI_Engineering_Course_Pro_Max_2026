"""Original interview practice for 11-llm-engineering/15-prompt-caching.

Local source: phases/11-llm-engineering/15-prompt-caching/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def lru_keys(accesses, capacity):
    """Replay string-key accesses in a cache of exact nonnegative integer capacity. Every access inserts/touches the key. Evict least recently used when full. Return final keys from least to most recent. capacity 0 returns []; invalid capacity raises ValueError."""
    raise NotImplementedError('TODO 1: lru_keys; see PROMPT.md')

def cache_replay(events, ttl):
    """Events have op put/get, key(str), time(number), plus value for put. ttl>=0 else ValueError. Put expiry=time+ttl. Return values for get events, None when absent or time>=expiry. Values are JSON-compatible and copied. Unknown op raises ValueError. Events are chronological."""
    raise NotImplementedError('TODO 2: cache_replay; see PROMPT.md')
