"""Original interview practice for 04-computer-vision/08-instance-segmentation-mask-rcnn.

Local source: phases/04-computer-vision/08-instance-segmentation-mask-rcnn/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def patchify(image, patch_size):
    """image is a nonempty rectangular 2D scalar matrix; both dimensions must be divisible by exact positive int patch_size. Return flattened patches in row-major patch order, pixels within each patch row-major. Invalid shape or size raises ValueError."""
    raise NotImplementedError('TODO 1: patchify; see PROMPT.md')

def box_iou(a, b):
    """Boxes are [x1,y1,x2,y2], with x2>=x1 and y2>=y1; reject other shapes/reversed bounds with ValueError. Return intersection area / union area, or 0 if union is zero. Touching edges have zero intersection."""
    raise NotImplementedError('TODO 2: box_iou; see PROMPT.md')
