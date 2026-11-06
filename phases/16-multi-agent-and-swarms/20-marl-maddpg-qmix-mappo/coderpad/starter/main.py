"""Original interview practice for 16-multi-agent-and-swarms/20-marl-maddpg-qmix-mappo.

Local source: phases/16-multi-agent-and-swarms/20-marl-maddpg-qmix-mappo/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def q_update(current, reward, next_values, alpha, gamma, terminal=False):
    """Require alpha,gamma in [0,1]. For terminal transition target=reward and next_values may be empty; otherwise require nonempty next_values and target=reward+gamma*max(next_values). Return current+alpha*(target-current). Invalid inputs raise ValueError."""
    raise NotImplementedError('TODO 1: q_update; see PROMPT.md')

def quorum_vote(votes, members, required):
    """votes is [[member,value],...]; members is a unique member-id list. Ignore exact repeated votes; conflicting votes from one member or a nonmember raise ValueError. required exact int >len(members)/2 and <=len(members). Return the value with at least required distinct voters, else None. Values are strings."""
    raise NotImplementedError('TODO 2: quorum_vote; see PROMPT.md')
