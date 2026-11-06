"""Offline diarization: agglomerative clustering of segment embeddings, and cutting the tree.

A dendrogram is written as nested tuples. A leaf is a segment index (int). A merge is
(left, right, similarity): two subtrees joined at that linkage similarity.
"""
from __future__ import annotations

from typing import Union

from .embed import cosine, l2_normalize

Dendrogram = Union[int, tuple["Dendrogram", "Dendrogram", float]]


def agglomerate(embeddings: list[list[float]]) -> Dendrogram:
    """Centroid-linkage agglomerative clustering on cosine similarity.

    Every segment starts as its own cluster. The two clusters whose centroids (means of their
    unit-length embeddings) are most similar merge, until one tree is left. Ties go to the pair
    that comes first.
    """
    if not embeddings:
        raise ValueError("nothing to cluster")
    clusters: list[tuple[Dendrogram, list[float]]] = [
        (index, l2_normalize(e)) for index, e in enumerate(embeddings)
    ]
    while len(clusters) > 1:
        best = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                sim = cosine(clusters[i][1], clusters[j][1])
                if best is None or sim > best[0]:
                    best = (sim, i, j)
        sim, i, j = best
        (left, left_sum), (right, right_sum) = clusters[i], clusters[j]
        clusters[i] = ((left, right, sim), [a + b for a, b in zip(left_sum, right_sum)])
        del clusters[j]
    return clusters[0][0]


def cut(tree: Dendrogram, threshold: float) -> list[list[int]]:
    """Flat clusters from a dendrogram.

    A subtree is one cluster when every merge inside it has similarity at least threshold;
    otherwise its two halves are cut on their own. Each cluster is a sorted list of segment
    indices, and clusters are ordered by their first index. A segment index that appears twice
    raises ValueError. Trees can be thousands of merges deep.
    """
    raise NotImplementedError
