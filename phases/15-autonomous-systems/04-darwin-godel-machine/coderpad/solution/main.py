"""Original interview practice for 15-autonomous-systems/04-darwin-godel-machine.

Local source: phases/15-autonomous-systems/04-darwin-godel-machine/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
import hashlib

def select_ucb(means, visits, total, exploration):
    if not means or len(means) != len(visits) or type(total) is not int or (total < 1) or (exploration < 0) or any((type(v) is not int or v < 0 for v in visits)):
        raise ValueError('UCB')
    if 0 in visits:
        return visits.index(0)
    return max(range(len(means)), key=lambda i: means[i] + exploration * math.sqrt(math.log(total) / visits[i]))

def manifest(files):
    if any((p.startswith('/') or '..' in p.split('/') for p in files)):
        raise ValueError('path')
    return {p: hashlib.sha256(files[p].encode()).hexdigest() for p in sorted(files)}
