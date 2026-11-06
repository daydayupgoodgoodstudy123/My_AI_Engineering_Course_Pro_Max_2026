"""Original interview practice for 04-computer-vision/06-object-detection-yolo.

Local source: phases/04-computer-vision/06-object-detection-yolo/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def box_iou(a, b):
    if any((len(x) != 4 or x[2] < x[0] or x[3] < x[1] for x in (a, b))):
        raise ValueError('box')
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union else 0

def nms(boxes, scores, threshold):
    if len(boxes) != len(scores) or not 0 <= threshold <= 1:
        raise ValueError('contract')
    kept = []
    for i in sorted(range(len(boxes)), key=lambda i: (-scores[i], i)):
        keep = True
        for j in kept:
            a, b = (boxes[i], boxes[j])
            inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
            union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
            if inter / union > threshold:
                keep = False
                break
        if keep:
            kept.append(i)
    return kept
