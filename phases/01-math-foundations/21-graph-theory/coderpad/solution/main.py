"""Original interview practice for 01-math-foundations/21-graph-theory.

Local source: phases/01-math-foundations/21-graph-theory/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
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

def topological_order(dependencies):
    pending = {n: set(ds) for n, ds in dependencies.items()}
    for ds in dependencies.values():
        for name in ds:
            pending.setdefault(name, set())
    result = []
    while pending:
        ready = sorted((n for n, ds in pending.items() if not ds))
        if not ready:
            raise ValueError('cycle')
        n = ready[0]
        result.append(n)
        del pending[n]
        for ds in pending.values():
            ds.discard(n)
    return result
