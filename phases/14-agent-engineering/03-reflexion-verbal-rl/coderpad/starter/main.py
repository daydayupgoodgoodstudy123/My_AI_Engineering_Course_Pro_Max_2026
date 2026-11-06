"""Original interview practice for 14-agent-engineering/03-reflexion-verbal-rl.

Local source: phases/14-agent-engineering/03-reflexion-verbal-rl/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def compact_memory(records, limit):
    """Records have id, timestamp, text. Keep the most recent record per id (later input wins timestamp ties), then retain limit records by descending timestamp and lexicographic id ties. Return copied records. limit exact nonnegative int; invalid limit raises ValueError."""
    raise NotImplementedError('TODO 1: compact_memory; see PROMPT.md')

def drift_report(baseline, current, tolerance):
    """baseline/current map identical metric keys to finite numbers. tolerance>=0. Return sorted keys with abs(current-baseline)>tolerance. Missing/additional keys or negative tolerance raises ValueError. Equality with tolerance is allowed."""
    raise NotImplementedError('TODO 2: drift_report; see PROMPT.md')
