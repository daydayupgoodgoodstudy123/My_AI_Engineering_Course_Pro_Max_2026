"""Original interview practice for 20-recursive-self-improvement/12-experience-streams-skill-libraries.

Local source: phases/20-recursive-self-improvement/12-experience-streams-skill-libraries/code/main.py (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import deque

def shortest_path(graph, start, goal):
    """graph maps string nodes to neighbor lists; missing nodes have no neighbors. Use BFS with neighbors sorted lexicographically and return the first shortest path including endpoints; return None if unreachable. start==goal returns [start]. Cycles must terminate."""
    raise NotImplementedError('TODO 1: shortest_path; see PROMPT.md')

def route_task(routes, query_tokens, role):
    """Each route has name(str), roles(list), keywords(list). Among role-eligible routes, score set intersection with query_tokens. Return unique highest positive-scoring name. No positive match or a tie returns None. Duplicate route names raise ValueError; input order must not resolve a tie."""
    raise NotImplementedError('TODO 2: route_task; see PROMPT.md')
