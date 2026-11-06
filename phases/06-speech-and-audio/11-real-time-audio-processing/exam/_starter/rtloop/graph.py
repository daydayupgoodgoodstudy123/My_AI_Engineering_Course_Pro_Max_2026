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
    raise NotImplementedError


def critical_path(graph: Graph, sink: str) -> tuple[int, list[str]]:
    """The slowest chain of inputs that ends at sink.

    A chain's latency is the sum of its stages' ms; reference edges add nothing. Returns
    (total ms, the stages of the chain from its first stage to sink). When inputs tie, the
    one listed first wins.
    """
    raise NotImplementedError
