"""Original interview practice for 07-transformers-deep-dive/04-positional-encoding.

Local source: phases/07-transformers-deep-dive/04-positional-encoding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def position_encoding(position, dimensions):
    if position < 0 or type(dimensions) is not int or dimensions <= 0 or dimensions % 2:
        raise ValueError('dimensions')
    result = []
    for i in range(dimensions // 2):
        angle = position / 10000 ** (2 * i / dimensions)
        result.extend([math.sin(angle), math.cos(angle)])
    return result

def transform(points, matrix, offset):
    if len(matrix) != 2 or any((len(r) != 2 for r in matrix)) or len(offset) != 2 or any((len(p) != 2 for p in points)):
        raise ValueError('shape')
    return [[sum((matrix[i][j] * p[j] for j in range(2))) + offset[i] for i in range(2)] for p in points]
