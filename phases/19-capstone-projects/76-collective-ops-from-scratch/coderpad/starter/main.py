"""Original interview practice for 19-capstone-projects/76-collective-ops-from-scratch.

Local source: phases/19-capstone-projects/76-collective-ops-from-scratch/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def allreduce(vectors, average=False):
    """Require a nonempty list of equal-length numeric vectors. Return elementwise sum, or mean if average is True. Ragged/empty worker lists raise ValueError; zero-length worker vectors are valid. No networking."""
    raise NotImplementedError('TODO 1: allreduce; see PROMPT.md')

def shard_bounds(total, workers):
    """Require exact ints total>=0 and workers>0. Return workers half-open [start,end] ranges covering 0..total without gaps; allocate one extra item to each earliest worker until the remainder is exhausted. Empty shards are allowed."""
    raise NotImplementedError('TODO 2: shard_bounds; see PROMPT.md')
