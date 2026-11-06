"""Original interview practice for 16-multi-agent-and-swarms/07-society-of-mind-debate.

Local source: phases/16-multi-agent-and-swarms/07-society-of-mind-debate/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

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

def unsupported_claims(claims, evidence_ids):
    if len({c['id'] for c in claims}) != len(claims):
        raise ValueError('duplicate claim')
    known = set(evidence_ids)
    return sorted((c['id'] for c in claims if not c['references'] or not set(c['references']) <= known))
