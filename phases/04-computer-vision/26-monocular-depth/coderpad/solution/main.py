"""Original interview practice for 04-computer-vision/26-monocular-depth.

Local source: phases/04-computer-vision/26-monocular-depth/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def depth_error(predicted, expected):
    if len(predicted) != len(expected):
        raise ValueError('shape')
    errors = [abs(p - t) / t for p, t in zip(predicted, expected) if t > 0]
    if not errors:
        raise ValueError('no valid depth')
    return sum(errors) / len(errors)

def mse(predicted, expected):
    if not predicted or len(predicted) != len(expected):
        raise ValueError('shape')
    return sum(((a - b) ** 2 for a, b in zip(predicted, expected))) / len(predicted)
