"""Original interview practice for 16-multi-agent-and-swarms/23-failure-modes-mast-groupthink.

Local source: phases/16-multi-agent-and-swarms/23-failure-modes-mast-groupthink/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def drift_report(baseline, current, tolerance):
    if set(baseline) != set(current) or tolerance < 0:
        raise ValueError('metrics')
    return sorted((k for k in baseline if abs(current[k] - baseline[k]) > tolerance))

def quorum_vote(votes, members, required):
    if type(required) is not int or not len(members) / 2 < required <= len(members):
        raise ValueError('quorum')
    seen = {}
    for member, value in votes:
        if member not in members or (member in seen and seen[member] != value):
            raise ValueError('vote')
        seen[member] = value
    counts = Counter(seen.values())
    return next((v for v, n in counts.items() if n >= required), None)
