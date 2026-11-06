"""Original interview practice for 04-computer-vision/21-keypoint-pose.

Local source: phases/04-computer-vision/21-keypoint-pose/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def heatmap_peak(heatmap):
    """Return [row,column] of the maximum in a nonempty rectangular 2D numeric heatmap. Ties choose earliest row-major cell. Empty or ragged heatmaps raise ValueError."""
    raise NotImplementedError('TODO 1: heatmap_peak; see PROMPT.md')

def transform(points, matrix, offset):
    """Apply 2x2 matrix and 2D offset to each 2D point. Return a new list of transformed points. Invalid matrix, offset, or point shapes raise ValueError. Empty points returns []."""
    raise NotImplementedError('TODO 2: transform; see PROMPT.md')
