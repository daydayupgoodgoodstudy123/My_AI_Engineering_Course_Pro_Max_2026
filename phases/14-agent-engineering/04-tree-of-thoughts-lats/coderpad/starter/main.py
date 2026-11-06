"""Original interview practice for 14-agent-engineering/04-tree-of-thoughts-lats.

Local source: phases/14-agent-engineering/04-tree-of-thoughts-lats/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
from collections import deque

def shortest_path(graph, start, goal):
    """graph maps string nodes to neighbor lists; missing nodes have no neighbors. Use BFS with neighbors sorted lexicographically and return the first shortest path including endpoints; return None if unreachable. start==goal returns [start]. Cycles must terminate."""
    raise NotImplementedError('TODO 1: shortest_path; see PROMPT.md')

def select_ucb(means, visits, total, exploration):
    """means/visits must be same-length nonempty lists; visits are exact nonnegative ints; total exact int >=1, exploration>=0. Return first unvisited index if any; else maximize mean+c*sqrt(log(total)/visits), ties lower index. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 2: select_ucb; see PROMPT.md')
