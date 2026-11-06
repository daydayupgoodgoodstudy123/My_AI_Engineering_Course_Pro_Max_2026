"""Tree-structured VQ: a codebook that is searched by walking down a tree."""
from __future__ import annotations

# A node is {"centroid": [floats], "children": [nodes]}. A node without children (no
# "children" key, or an empty list) is a leaf. The leaves are the codebook: codes number
# them 0, 1, 2, ... from left to right (depth first, children in list order).
Node = dict


def leaf_codebook(tree: Node) -> list[list[float]]:
    """Leaf centroids in code order."""
    raise NotImplementedError


def tree_search(tree: Node, vector: list[float]) -> tuple[int, int]:
    """Greedy descent from the root.

    At every internal node, step to the child whose centroid is nearest to vector (squared
    distance; ties go to the earlier child). Returns (code of the leaf reached, number of
    distances computed). This is not always the nearest leaf; full_search is. A vector of
    the wrong length raises ValueError.
    """
    raise NotImplementedError


def full_search(tree: Node, vector: list[float]) -> tuple[int, int]:
    """Nearest leaf by checking every leaf: (code, number of distances computed).

    Ties go to the lower code. A vector of the wrong length raises ValueError.
    """
    raise NotImplementedError
