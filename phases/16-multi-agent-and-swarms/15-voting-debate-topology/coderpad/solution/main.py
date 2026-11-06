"""Original interview practice for 16-multi-agent-and-swarms/15-voting-debate-topology.

Local source: phases/16-multi-agent-and-swarms/15-voting-debate-topology/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def majority_votes(predictions):
    if not predictions:
        return []
    if any((len(r) != len(predictions[0]) for r in predictions)):
        raise ValueError('shape')
    return [min(Counter(column), key=lambda x: (-Counter(column)[x], x)) for column in zip(*predictions)]

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
