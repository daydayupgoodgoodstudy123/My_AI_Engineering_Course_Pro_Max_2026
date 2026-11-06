"""Original interview practice for 12-multimodal-ai/17-video-language-temporal-grounding.

Local source: phases/12-multimodal-ai/17-video-language-temporal-grounding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def sample_frames(length, count):
    if type(length) is not int or type(count) is not int or (not 0 <= count <= length):
        raise ValueError('frames')
    if count == 0:
        return []
    if count == 1:
        return [0]
    return [i * (length - 1) // (count - 1) for i in range(count)]

def box_iou(a, b):
    if any((len(x) != 4 or x[2] < x[0] or x[3] < x[1] for x in (a, b))):
        raise ValueError('box')
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union else 0
