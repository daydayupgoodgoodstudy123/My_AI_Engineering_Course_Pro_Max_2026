"""Original interview practice for 04-computer-vision/21-keypoint-pose.

Local source: phases/04-computer-vision/21-keypoint-pose/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def heatmap_peak(heatmap):
    if not heatmap or not heatmap[0] or any((len(r) != len(heatmap[0]) for r in heatmap)):
        raise ValueError('heatmap')
    return list(max(((i, j) for i in range(len(heatmap)) for j in range(len(heatmap[0]))), key=lambda p: heatmap[p[0]][p[1]]))

def transform(points, matrix, offset):
    if len(matrix) != 2 or any((len(r) != 2 for r in matrix)) or len(offset) != 2 or any((len(p) != 2 for p in points)):
        raise ValueError('shape')
    return [[sum((matrix[i][j] * p[j] for j in range(2))) + offset[i] for i in range(2)] for p in points]
