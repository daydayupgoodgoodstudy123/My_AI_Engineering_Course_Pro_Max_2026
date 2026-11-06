"""Original interview practice for 10-llms-from-scratch/19-dualpipe-parallelism.

Local source: phases/10-llms-from-scratch/19-dualpipe-parallelism/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def pipeline_bubble(stages, microbatches):
    """Both arguments are exact positive ints. Return idle fraction (stages-1)/(microbatches+stages-1) for a simplified flush schedule; invalid input raises ValueError. No actual distributed execution."""
    raise NotImplementedError('TODO 1: pipeline_bubble; see PROMPT.md')

def shard_bounds(total, workers):
    """Require exact ints total>=0 and workers>0. Return workers half-open [start,end] ranges covering 0..total without gaps; allocate one extra item to each earliest worker until the remainder is exhausted. Empty shards are allowed."""
    raise NotImplementedError('TODO 2: shard_bounds; see PROMPT.md')
