"""Original interview practice for 04-computer-vision/24-sam3-open-vocab-segmentation.

Local source: phases/04-computer-vision/24-sam3-open-vocab-segmentation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def rle_encode(values):
    """Return consecutive [value,count] runs for a list of exact booleans. Empty list returns []; reject non-bool elements with ValueError. Preserve runs and original order."""
    raise NotImplementedError('TODO 1: rle_encode; see PROMPT.md')

def dice(predicted, expected):
    """Require equal-length exact-bool masks. Dice=2*intersection/(predicted positives+expected positives); if both have no positives return 1. Invalid masks raise ValueError."""
    raise NotImplementedError('TODO 2: dice; see PROMPT.md')
