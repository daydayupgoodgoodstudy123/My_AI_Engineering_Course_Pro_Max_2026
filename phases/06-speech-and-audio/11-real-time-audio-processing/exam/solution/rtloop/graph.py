"""Plan the audio processing graph: the order stages run in, and the chain that sets the latency."""
from __future__ import annotations

# {stage: {"ms": processing latency,
#          "inputs": [stages whose output for this frame it reads],
#          "reference": [stages whose previous frames it reads, like an AEC's far-end feed]}}
Graph = dict[str, dict]


def schedule(graph: Graph) -> list[str]:
    """Every stage once, each one after all of its inputs: the order a frame is processed in.

    Reference edges carry earlier frames, so they do not order stages, and a loop through one
    is fine. Any other loop raises ValueError naming the stages in the loop, and so does an
    input or a reference that is not a stage of the graph.
    """
    _check_names(graph)
    order: list[str] = []
    done: set[str] = set()
    path: list[str] = []

    def visit(name: str) -> None:
        if name in done:
            return
        if name in path:
            loop = path[path.index(name) :] + [name]
            raise ValueError("loop of inputs: " + " -> ".join(loop))
        path.append(name)
        for upstream in graph[name].get("inputs", []):
            visit(upstream)
        path.pop()
        done.add(name)
        order.append(name)

    for name in graph:
        visit(name)
    return order


def critical_path(graph: Graph, sink: str) -> tuple[int, list[str]]:
    """The slowest chain of inputs that ends at sink.

    A chain's latency is the sum of its stages' ms; reference edges add nothing. Returns
    (total ms, the stages of the chain from its first stage to sink). When inputs tie, the
    one listed first wins.
    """
    best: dict[str, tuple[int, list[str]]] = {}
    for name in schedule(graph):
        inputs = graph[name].get("inputs", [])
        total, chain = max((best[i] for i in inputs), key=lambda tc: tc[0], default=(0, []))
        best[name] = (total + graph[name]["ms"], chain + [name])
    if sink not in best:
        raise ValueError(f"unknown stage {sink!r}")
    return best[sink]


def _check_names(graph: Graph) -> None:
    for name, spec in graph.items():
        for upstream in [*spec.get("inputs", []), *spec.get("reference", [])]:
            if upstream not in graph:
                raise ValueError(f"{name!r} reads from unknown stage {upstream!r}")
