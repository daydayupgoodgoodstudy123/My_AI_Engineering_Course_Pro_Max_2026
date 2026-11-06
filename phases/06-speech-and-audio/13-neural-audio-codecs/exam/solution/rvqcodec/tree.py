"""Tree-structured VQ: a codebook that is searched by walking down a tree."""
from __future__ import annotations

# A node is {"centroid": [floats], "children": [nodes]}. A node without children (no
# "children" key, or an empty list) is a leaf. The leaves are the codebook: codes number
# them 0, 1, 2, ... from left to right (depth first, children in list order).
Node = dict


def _children(node: Node) -> list[Node]:
    return node.get("children") or []


def _distance(vector: list[float], node: Node) -> float:
    centroid = node["centroid"]
    if len(centroid) != len(vector):
        raise ValueError(f"vector has {len(vector)} values, centroid has {len(centroid)}")
    return sum((x - y) ** 2 for x, y in zip(vector, centroid))


def _n_leaves(node: Node) -> int:
    children = _children(node)
    return sum(_n_leaves(child) for child in children) if children else 1


def leaf_codebook(tree: Node) -> list[list[float]]:
    """Leaf centroids in code order."""
    children = _children(tree)
    if not children:
        return [tree["centroid"]]
    return [centroid for child in children for centroid in leaf_codebook(child)]


def tree_search(tree: Node, vector: list[float]) -> tuple[int, int]:
    """Greedy descent from the root.

    At every internal node, step to the child whose centroid is nearest to vector (squared
    distance; ties go to the earlier child). Returns (code of the leaf reached, number of
    distances computed). This is not always the nearest leaf; full_search is. A vector of
    the wrong length raises ValueError.
    """
    node, code, computed = tree, 0, 0
    while children := _children(node):
        distances = [_distance(vector, child) for child in children]
        computed += len(children)
        best = min(range(len(children)), key=distances.__getitem__)
        code += sum(_n_leaves(child) for child in children[:best])
        node = children[best]
    return code, computed


def full_search(tree: Node, vector: list[float]) -> tuple[int, int]:
    """Nearest leaf by checking every leaf: (code, number of distances computed).

    Ties go to the lower code. A vector of the wrong length raises ValueError.
    """
    leaves = [{"centroid": centroid} for centroid in leaf_codebook(tree)]
    distances = [_distance(vector, leaf) for leaf in leaves]
    return min(range(len(leaves)), key=distances.__getitem__), len(leaves)
