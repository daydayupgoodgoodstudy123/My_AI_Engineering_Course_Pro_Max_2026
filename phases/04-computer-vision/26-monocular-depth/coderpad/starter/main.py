"""Original interview practice for 04-computer-vision/26-monocular-depth.

Local source: phases/04-computer-vision/26-monocular-depth/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def depth_error(predicted, expected):
    """Lists have equal lengths. Evaluate only positions where expected>0; return mean(abs(pred-true)/true). No valid ground truth or mismatched lengths raises ValueError."""
    raise NotImplementedError('TODO 1: depth_error; see PROMPT.md')

def mse(predicted, expected):
    """Return mean squared error of equal-length nonempty numeric lists. Unequal lengths or empty inputs raise ValueError."""
    raise NotImplementedError('TODO 2: mse; see PROMPT.md')
