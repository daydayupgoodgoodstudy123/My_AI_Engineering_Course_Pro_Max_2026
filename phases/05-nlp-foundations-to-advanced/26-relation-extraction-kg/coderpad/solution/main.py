"""Original interview practice for 05-nlp-foundations-to-advanced/26-relation-extraction-kg.

Local source: phases/05-nlp-foundations-to-advanced/26-relation-extraction-kg/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import deque

def unsupported_claims(claims, evidence_ids):
    if len({c['id'] for c in claims}) != len(claims):
        raise ValueError('duplicate claim')
    known = set(evidence_ids)
    return sorted((c['id'] for c in claims if not c['references'] or not set(c['references']) <= known))

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
