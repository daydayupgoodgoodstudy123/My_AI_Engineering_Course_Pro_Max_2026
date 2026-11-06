"""Source metrics and Matryoshka-style projection on supplied numeric vectors."""
import math
from .records import pair_values, vector_value, dimension_value, count_value

def norm(vector):
    """Given scaled-sum norm; a nonzero finite coordinate never becomes zero."""
    return math.hypot(*vector)

def direction_scale(vector):
    """Given finite-direction coordinates with largest absolute value one."""
    scale = max(abs(value) for value in vector)
    return tuple(value / scale for value in vector) if scale else tuple(vector)

def unit_direction(vector):
    """Given stable normalization, including subnormals and overflowing norms."""
    scaled = direction_scale(vector)
    length = norm(scaled)
    return tuple(value / length for value in scaled) if length else scaled

def truncate_embedding(vector, dimensions):
    """Take the first dimensions and normalize that prefix; zero stays zero.

    This simulates projection mechanics only; no trained Matryoshka model.
    Dimensions are positive and cannot exceed the original vector length.
    """
    vector = vector_value(vector)
    dimension_value(dimensions)
    if dimensions > len(vector):
        raise ValueError("projection exceeds original dimension")
    truncated = vector[:dimensions]
    return unit_direction(truncated)

def binarize(vector):
    """Return source sign bits: positive ->1; negative and either zero ->0."""
    return tuple(1 if value > 0 else 0 for value in vector_value(vector))

def cosine_similarity(a, b):
    """Cosine for equal positive dimensions; either zero vector yields 0.

    Preserve magnitude independence; do not assume supplied vectors are unit.
    """
    a, b = pair_values(a, b)
    a, b = direction_scale(a), direction_scale(b)
    norm_a = norm(a)
    norm_b = norm(b)
    dot = 0.0
    for left, right in zip(a, b):
        dot += left * right
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

def metric_value(a, b, metric):
    """Given dispatch: cosine/dot are similarities, euclidean/hamming distances."""
    a, b = pair_values(a, b)
    if metric == "cosine":
        return cosine_similarity(a, b)
    if metric == "dot":
        return sum(x * y for x, y in zip(a, b))
    if metric == "euclidean":
        return math.dist(a, b)
    if metric == "hamming":
        return sum(x != y for x, y in zip(binarize(a), binarize(b)))
    raise ValueError("unknown metric")

def score_key(score, index, metric):
    """Given common rank key; raw distances smaller, similarities larger."""
    if metric not in ("cosine", "dot", "euclidean", "hamming"):
        raise ValueError("unknown metric")
    return (score if metric in ("euclidean", "hamming") else -score, index)

def order_hits(hits, metric):
    """Rank raw metric values; all equal scores retain original bank order."""
    return sorted(hits, key=lambda hit: score_key(hit["score"], hit["index"], metric))

def search_vectors(query, records, top_k, metric="cosine"):
    """Given scan over already validated records; delegates metric ordering."""
    count_value(top_k)
    hits = [{"key": record.key, "index": index, "score": metric_value(query, record.vector, metric)} for index, record in enumerate(records)]
    return order_hits(hits, metric)[:top_k]
