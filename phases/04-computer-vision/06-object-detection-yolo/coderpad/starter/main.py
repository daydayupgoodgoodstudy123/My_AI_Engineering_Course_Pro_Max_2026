"""Original interview practice for 04-computer-vision/06-object-detection-yolo.

Local source: phases/04-computer-vision/06-object-detection-yolo/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def box_iou(a, b):
    """Boxes are [x1,y1,x2,y2], with x2>=x1 and y2>=y1; reject other shapes/reversed bounds with ValueError. Return intersection area / union area, or 0 if union is zero. Touching edges have zero intersection."""
    raise NotImplementedError('TODO 1: box_iou; see PROMPT.md')

def nms(boxes, scores, threshold):
    """Return kept original box indices, selecting descending score with original-index ties. Suppress candidates with IoU strictly >threshold against a kept box. Boxes are valid positive-area xyxy; reject unequal lengths or threshold outside [0,1]. Empty inputs return []."""
    raise NotImplementedError('TODO 2: nms; see PROMPT.md')
