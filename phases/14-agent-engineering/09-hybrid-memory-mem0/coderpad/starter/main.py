"""Original interview practice for 14-agent-engineering/09-hybrid-memory-mem0.

Local source: phases/14-agent-engineering/09-hybrid-memory-mem0/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def cache_replay(events, ttl):
    """Events have op put/get, key(str), time(number), plus value for put. ttl>=0 else ValueError. Put expiry=time+ttl. Return values for get events, None when absent or time>=expiry. Values are JSON-compatible and copied. Unknown op raises ValueError. Events are chronological."""
    raise NotImplementedError('TODO 1: cache_replay; see PROMPT.md')

def rrf(rankings, constant=60):
    """For each ranking, score each id once at its FIRST 1-based rank using 1/(constant+rank). Sum across lists. Return ids sorted by descending total score, then lexicographic id. constant>=0 else ValueError; empty rankings yields []."""
    raise NotImplementedError('TODO 2: rrf; see PROMPT.md')
