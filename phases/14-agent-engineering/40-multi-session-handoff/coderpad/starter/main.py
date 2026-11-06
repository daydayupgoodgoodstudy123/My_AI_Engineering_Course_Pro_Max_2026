"""Original interview practice for 14-agent-engineering/40-multi-session-handoff.

Local source: phases/14-agent-engineering/40-multi-session-handoff/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def validate_handoff(bundle):
    """Required nonempty string fields: objective, state, next_action. checks must be a nonempty list of nonempty strings. Return sorted missing/invalid field names (among those four). Extra fields allowed; whitespace-only strings are invalid. Do not execute next_action."""
    raise NotImplementedError('TODO 1: validate_handoff; see PROMPT.md')

def compact_memory(records, limit):
    """Records have id, timestamp, text. Keep the most recent record per id (later input wins timestamp ties), then retain limit records by descending timestamp and lexicographic id ties. Return copied records. limit exact nonnegative int; invalid limit raises ValueError."""
    raise NotImplementedError('TODO 2: compact_memory; see PROMPT.md')
