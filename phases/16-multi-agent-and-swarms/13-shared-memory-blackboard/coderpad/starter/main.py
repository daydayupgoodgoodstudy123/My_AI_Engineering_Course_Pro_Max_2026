"""Original interview practice for 16-multi-agent-and-swarms/13-shared-memory-blackboard.

Local source: phases/16-multi-agent-and-swarms/13-shared-memory-blackboard/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def compact_memory(records, limit):
    """Records have id, timestamp, text. Keep the most recent record per id (later input wins timestamp ties), then retain limit records by descending timestamp and lexicographic id ties. Return copied records. limit exact nonnegative int; invalid limit raises ValueError."""
    raise NotImplementedError('TODO 1: compact_memory; see PROMPT.md')

def cache_replay(events, ttl):
    """Events have op put/get, key(str), time(number), plus value for put. ttl>=0 else ValueError. Put expiry=time+ttl. Return values for get events, None when absent or time>=expiry. Values are JSON-compatible and copied. Unknown op raises ValueError. Events are chronological."""
    raise NotImplementedError('TODO 2: cache_replay; see PROMPT.md')
