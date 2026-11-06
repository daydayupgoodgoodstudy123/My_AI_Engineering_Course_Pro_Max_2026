"""Given strict matrix primitives using the course row-vector convention."""
import math
def matrix(value):
    rows=tuple(tuple(row) for row in value)
    if not rows or not rows[0] or any(len(row)!=len(rows[0]) for row in rows):raise ValueError("matrix must be nonempty and rectangular")
    if any(type(x) not in (float,int) or not math.isfinite(x) for row in rows for x in row):raise ValueError("finite numeric matrix required")
    return rows
def matmul(left,right):
    """Multiply strict rectangular matrices; incompatible inner dimensions are rejected."""
    if len(left[0])!=len(right):raise ValueError("matrix inner dimensions disagree")
    columns=tuple(zip(*right))
    return tuple(tuple(sum(a*b for a,b in zip(row,col)) for col in columns) for row in left)
def vecmat(vector,right):
    if len(vector)!=len(right):raise ValueError("vector input dimension disagrees")
    return tuple(sum(a*b for a,b in zip(vector,col)) for col in zip(*right))
