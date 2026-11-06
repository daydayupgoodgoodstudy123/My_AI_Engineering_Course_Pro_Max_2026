"""Original interview practice for 01-math-foundations/21-graph-theory.

Local source: phases/01-math-foundations/21-graph-theory/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import deque

def shortest_path(graph, start, goal):
    """graph maps string nodes to neighbor lists; missing nodes have no neighbors. Use BFS with neighbors sorted lexicographically and return the first shortest path including endpoints; return None if unreachable. start==goal returns [start]. Cycles must terminate."""
    raise NotImplementedError('TODO 1: shortest_path; see PROMPT.md')

def topological_order(dependencies):
    """dependencies maps node string to prerequisite-name list. Include names appearing only as prerequisites. Return lexicographically smallest available node at each step. Cycles raise ValueError. Duplicate dependencies count once; empty graph returns []."""
    raise NotImplementedError('TODO 2: topological_order; see PROMPT.md')
