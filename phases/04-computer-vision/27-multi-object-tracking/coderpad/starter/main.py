"""Original interview practice for 04-computer-vision/27-multi-object-tracking.

Local source: phases/04-computer-vision/27-multi-object-tracking/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def box_iou(a, b):
    """Boxes are [x1,y1,x2,y2], with x2>=x1 and y2>=y1; reject other shapes/reversed bounds with ValueError. Return intersection area / union area, or 0 if union is zero. Touching edges have zero intersection."""
    raise NotImplementedError('TODO 1: box_iou; see PROMPT.md')

def transition(state, target):
    """Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves."""
    raise NotImplementedError('TODO 2: transition; see PROMPT.md')
