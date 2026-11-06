"""Find the smallest missing real-workflow slice in a finite DAG."""
from __future__ import annotations

def validate_workflow(graph: dict[str,tuple[str,...]], trigger: str, outcomes: set[str]) -> None:
    """Supplied: all endpoints must exist and the entire finite graph is acyclic."""
    if trigger not in graph or not outcomes<=set(graph):raise ValueError('unknown workflow endpoint')
    visiting=set();done=set()
    def visit(node):
        if node not in graph:raise ValueError('unknown workflow node')
        if node in visiting:raise ValueError('workflow cycle')
        if node in done:return
        visiting.add(node)
        for child in graph[node]:visit(child)
        visiting.remove(node);done.add(node)
    for node in graph:visit(node)

def minimum_completion(graph: dict[str,tuple[str,...]], trigger: str, outcomes: set[str], built: set[str]) -> dict | None:
    """Find a connected trigger-to-any-outcome path minimizing nodes not yet built,
    including both endpoints. Tie-break by the complete tuple of node ids, not child
    cost alone. Stop at the first outcome on a path. Return {'path': tuple, 'missing':
    tuple in path order}; unreachable outcomes yield None. Extra built nodes do not
    require inclusion. Use supplied DAG validation; do not mutate any input.
    """
    validate_workflow(graph,trigger,outcomes)
    memo={}
    def visit(node):
        if node in memo:return memo[node]
        if node in outcomes:best=(int(node not in built),(node,))
        else:
            options=[]
            for child in graph[node]:
                tail=visit(child)
                if tail is not None:options.append((int(node not in built)+tail[0],(node,)+tail[1]))
            best=min(options) if options else None
        memo[node]=best
        return best
    result=visit(trigger)
    if result is None:return None
    path=result[1]
    return {'path':path,'missing':tuple(node for node in path if node not in built)}
