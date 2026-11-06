"""Original interview practice for 10-llms-from-scratch/19-dualpipe-parallelism.

Local source: phases/10-llms-from-scratch/19-dualpipe-parallelism/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def pipeline_bubble(stages, microbatches):
    if any((type(x) is not int or x <= 0 for x in (stages, microbatches))):
        raise ValueError('pipeline')
    return (stages - 1) / (microbatches + stages - 1)

def shard_bounds(total, workers):
    if type(total) is not int or type(workers) is not int or total < 0 or (workers <= 0):
        raise ValueError('shape')
    q, r = divmod(total, workers)
    start = 0
    result = []
    for i in range(workers):
        end = start + q + (i < r)
        result.append([start, end])
        start = end
    return result
