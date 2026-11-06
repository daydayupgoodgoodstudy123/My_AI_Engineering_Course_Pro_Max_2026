"""Original interview practice for 04-computer-vision/22-3d-gaussian-splatting.

Local source: phases/04-computer-vision/22-3d-gaussian-splatting/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def transform(points, matrix, offset):
    """Apply 2x2 matrix and 2D offset to each 2D point. Return a new list of transformed points. Invalid matrix, offset, or point shapes raise ValueError. Empty points returns []."""
    raise NotImplementedError('TODO 1: transform; see PROMPT.md')

def flow_step(state, velocity, delta):
    """Return state+delta*velocity coordinatewise. Require equal lengths and numeric delta in [0,1]; otherwise ValueError. Empty vectors are valid."""
    raise NotImplementedError('TODO 2: flow_step; see PROMPT.md')
