"""Original interview practice for 14-agent-engineering/03-reflexion-verbal-rl.

Local source: phases/14-agent-engineering/03-reflexion-verbal-rl/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def compact_memory(records, limit):
    if type(limit) is not int or limit < 0:
        raise ValueError('limit')
    latest = {}
    for r in records:
        if r['id'] not in latest or r['timestamp'] >= latest[r['id']]['timestamp']:
            latest[r['id']] = r
    return copy.deepcopy(sorted(latest.values(), key=lambda r: (-r['timestamp'], r['id']))[:limit])

def drift_report(baseline, current, tolerance):
    if set(baseline) != set(current) or tolerance < 0:
        raise ValueError('metrics')
    return sorted((k for k in baseline if abs(current[k] - baseline[k]) > tolerance))
