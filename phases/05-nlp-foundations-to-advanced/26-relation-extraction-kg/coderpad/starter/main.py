"""Original interview practice for 05-nlp-foundations-to-advanced/26-relation-extraction-kg.

Local source: phases/05-nlp-foundations-to-advanced/26-relation-extraction-kg/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import deque

def unsupported_claims(claims, evidence_ids):
    """Claims have unique id(str) and references(list of evidence ids). Return sorted claim ids lacking references or containing any unknown reference. Duplicate claim ids raises ValueError. Having a reference verifies linkage only, not factual truth."""
    raise NotImplementedError('TODO 1: unsupported_claims; see PROMPT.md')

def shortest_path(graph, start, goal):
    """graph maps string nodes to neighbor lists; missing nodes have no neighbors. Use BFS with neighbors sorted lexicographically and return the first shortest path including endpoints; return None if unreachable. start==goal returns [start]. Cycles must terminate."""
    raise NotImplementedError('TODO 2: shortest_path; see PROMPT.md')
