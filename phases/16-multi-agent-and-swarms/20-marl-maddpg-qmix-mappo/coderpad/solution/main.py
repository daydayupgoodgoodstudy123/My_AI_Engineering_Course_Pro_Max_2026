"""Original interview practice for 16-multi-agent-and-swarms/20-marl-maddpg-qmix-mappo.

Local source: phases/16-multi-agent-and-swarms/20-marl-maddpg-qmix-mappo/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def q_update(current, reward, next_values, alpha, gamma, terminal=False):
    if not 0 <= alpha <= 1 or not 0 <= gamma <= 1 or (not terminal and (not next_values)):
        raise ValueError('transition')
    target = reward + (0 if terminal else gamma * max(next_values))
    return current + alpha * (target - current)

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
