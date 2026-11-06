"""Original interview practice for 16-multi-agent-and-swarms/09-parallel-swarm-networks.

Local source: phases/16-multi-agent-and-swarms/09-parallel-swarm-networks/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


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

def allreduce(vectors, average=False):
    if not vectors or any((len(v) != len(vectors[0]) for v in vectors)):
        raise ValueError('shape')
    return [sum(column) / (len(vectors) if average else 1) for column in zip(*vectors)]
