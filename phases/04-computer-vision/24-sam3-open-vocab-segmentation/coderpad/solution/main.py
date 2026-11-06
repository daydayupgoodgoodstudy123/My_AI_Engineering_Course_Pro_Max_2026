"""Original interview practice for 04-computer-vision/24-sam3-open-vocab-segmentation.

Local source: phases/04-computer-vision/24-sam3-open-vocab-segmentation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def rle_encode(values):
    if any((type(x) is not bool for x in values)):
        raise ValueError('mask')
    runs = []
    for x in values:
        if runs and runs[-1][0] == x:
            runs[-1][1] += 1
        else:
            runs.append([x, 1])
    return runs

def dice(predicted, expected):
    if len(predicted) != len(expected) or any((type(x) is not bool for x in predicted + expected)):
        raise ValueError('mask')
    den = sum(predicted) + sum(expected)
    return 2 * sum((a and b for a, b in zip(predicted, expected))) / den if den else 1
