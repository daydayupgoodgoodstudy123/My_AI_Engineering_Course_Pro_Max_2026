"""Original interview practice for 04-computer-vision/02-convolutions-from-scratch.

Local source: phases/04-computer-vision/02-convolutions-from-scratch/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def convolve(signal, kernel, stride=1):
    """Compute valid 1D cross-correlation (kernel is NOT reversed) using exact positive integer stride. Empty kernel or invalid stride raises ValueError. Kernel longer than signal yields []."""
    raise NotImplementedError('TODO 1: convolve; see PROMPT.md')

def max_pool(values, width):
    """Use non-overlapping windows of exact positive integer width. Include a shorter final window. Return max per window; empty input yields []. Invalid width raises ValueError."""
    raise NotImplementedError('TODO 2: max_pool; see PROMPT.md')
