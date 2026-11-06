"""Given vector/metadata shapes and argument checks; no embedding model."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class VectorRecord:
    key: str
    vector: tuple[float, ...]
    metadata: dict[str, str]

def dimension_value(dimension):
    if type(dimension) is not int or dimension <= 0:
        raise ValueError("dimension must be a positive integer")
    return dimension

def count_value(count):
    if type(count) is not int or count < 0:
        raise ValueError("count must be a nonnegative integer")
    return count

def vector_value(vector, dimension=None):
    values = tuple(vector)
    if not values or (dimension is not None and len(values) != dimension):
        raise ValueError("vector dimension mismatch")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise ValueError("vectors require finite numeric coordinates")
    return values

def pair_values(a, b):
    a = vector_value(a)
    return a, vector_value(b, len(a))

def records_value(records, dimension):
    """Validate a finite bank before mutation; preserve declaration order."""
    dimension_value(dimension)
    result = list(records)
    seen = set()
    for record in result:
        if not isinstance(record, VectorRecord) or not isinstance(record.key, str) or not record.key or record.key in seen:
            raise ValueError("records require distinct nonempty keys")
        seen.add(record.key)
        vector_value(record.vector, dimension)
        if not isinstance(record.metadata, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in record.metadata.items()):
            raise ValueError("metadata must map strings to strings")
    return result

def dense_metric(metric):
    if metric not in ("cosine", "dot", "euclidean"):
        raise ValueError("unsupported dense metric")
    return metric
