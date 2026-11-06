"""Original interview practice for 16-multi-agent-and-swarms/19-swarm-optimization-pso-aco.

Local source: phases/16-multi-agent-and-swarms/19-swarm-optimization-pso-aco/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def top_k(scores, k):
    """Return the indices of k largest scores, descending score with lower original index ties. k exact int in [0,len(scores)], else ValueError; k=0 returns []."""
    raise NotImplementedError('TODO 1: top_k; see PROMPT.md')

def pareto_front(candidates):
    """Candidates have unique id strings, quality higher-is-better, cost lower-is-better. Return sorted ids not dominated by another candidate that is no worse in both and strictly better in at least one. Equal quality/cost entries both survive; empty input yields []."""
    raise NotImplementedError('TODO 2: pareto_front; see PROMPT.md')
