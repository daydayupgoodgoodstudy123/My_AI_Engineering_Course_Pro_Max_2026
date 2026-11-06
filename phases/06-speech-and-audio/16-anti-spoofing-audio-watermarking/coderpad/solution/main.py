"""Original interview practice for 06-speech-and-audio/16-anti-spoofing-audio-watermarking.

Local source: phases/06-speech-and-audio/16-anti-spoofing-audio-watermarking/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bit_accuracy(expected, observed):
    if not expected or len(expected) != len(observed) or any((type(x) is not int or x not in (0, 1) for x in expected + observed)):
        raise ValueError('bits')
    return sum((a == b for a, b in zip(expected, observed))) / len(expected)

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
