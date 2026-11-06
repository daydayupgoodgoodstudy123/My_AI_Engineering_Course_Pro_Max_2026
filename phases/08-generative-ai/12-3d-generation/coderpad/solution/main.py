"""Original interview practice for 08-generative-ai/12-3d-generation.

Local source: phases/08-generative-ai/12-3d-generation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def transform(points, matrix, offset):
    if len(matrix) != 2 or any((len(r) != 2 for r in matrix)) or len(offset) != 2 or any((len(p) != 2 for p in points)):
        raise ValueError('shape')
    return [[sum((matrix[i][j] * p[j] for j in range(2))) + offset[i] for i in range(2)] for p in points]

def flow_step(state, velocity, delta):
    if len(state) != len(velocity) or not 0 <= delta <= 1:
        raise ValueError('contract')
    return [x + delta * v for x, v in zip(state, velocity)]
