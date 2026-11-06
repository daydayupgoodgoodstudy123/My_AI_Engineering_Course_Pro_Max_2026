"""Original interview practice for 16-multi-agent-and-swarms/23-failure-modes-mast-groupthink.

Local source: phases/16-multi-agent-and-swarms/23-failure-modes-mast-groupthink/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def drift_report(baseline, current, tolerance):
    """baseline/current map identical metric keys to finite numbers. tolerance>=0. Return sorted keys with abs(current-baseline)>tolerance. Missing/additional keys or negative tolerance raises ValueError. Equality with tolerance is allowed."""
    raise NotImplementedError('TODO 1: drift_report; see PROMPT.md')

def quorum_vote(votes, members, required):
    """votes is [[member,value],...]; members is a unique member-id list. Ignore exact repeated votes; conflicting votes from one member or a nonmember raise ValueError. required exact int >len(members)/2 and <=len(members). Return the value with at least required distinct voters, else None. Values are strings."""
    raise NotImplementedError('TODO 2: quorum_vote; see PROMPT.md')
