"""Original interview practice for 14-agent-engineering/04-tree-of-thoughts-lats.

Local source: phases/14-agent-engineering/04-tree-of-thoughts-lats/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import deque

def shortest_path(graph, start, goal):
    queue = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == goal:
            return path
        for nxt in sorted(graph.get(node, [])):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(path + [nxt])
    return None

def select_ucb(means, visits, total, exploration):
    if not means or len(means) != len(visits) or type(total) is not int or (total < 1) or (exploration < 0) or any((type(v) is not int or v < 0 for v in visits)):
        raise ValueError('UCB')
    if 0 in visits:
        return visits.index(0)
    return max(range(len(means)), key=lambda i: means[i] + exploration * math.sqrt(math.log(total) / visits[i]))
