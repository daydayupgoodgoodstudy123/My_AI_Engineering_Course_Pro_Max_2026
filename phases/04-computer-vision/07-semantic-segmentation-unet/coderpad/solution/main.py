"""Original interview practice for 04-computer-vision/07-semantic-segmentation-unet.

Local source: phases/04-computer-vision/07-semantic-segmentation-unet/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def dice(predicted, expected):
    if len(predicted) != len(expected) or any((type(x) is not bool for x in predicted + expected)):
        raise ValueError('mask')
    den = sum(predicted) + sum(expected)
    return 2 * sum((a and b for a, b in zip(predicted, expected))) / den if den else 1

def classification(expected, predicted):
    if len(expected) != len(predicted) or any((type(x) is not bool for x in expected + predicted)):
        raise ValueError('labels')
    tp = sum((a and b for a, b in zip(expected, predicted)))
    fp = sum((not a and b for a, b in zip(expected, predicted)))
    fn = sum((a and (not b) for a, b in zip(expected, predicted)))
    tn = len(expected) - tp - fp - fn
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'precision': p, 'recall': r, 'f1': 2 * p * r / (p + r) if p + r else 0}
