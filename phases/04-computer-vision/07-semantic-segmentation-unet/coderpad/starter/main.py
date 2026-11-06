"""Original interview practice for 04-computer-vision/07-semantic-segmentation-unet.

Local source: phases/04-computer-vision/07-semantic-segmentation-unet/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def dice(predicted, expected):
    """Require equal-length exact-bool masks. Dice=2*intersection/(predicted positives+expected positives); if both have no positives return 1. Invalid masks raise ValueError."""
    raise NotImplementedError('TODO 1: dice; see PROMPT.md')

def classification(expected, predicted):
    """Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError."""
    raise NotImplementedError('TODO 2: classification; see PROMPT.md')
