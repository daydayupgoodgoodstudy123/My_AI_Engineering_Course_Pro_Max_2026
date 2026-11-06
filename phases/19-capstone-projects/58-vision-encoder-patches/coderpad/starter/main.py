"""Original interview practice for 19-capstone-projects/58-vision-encoder-patches.

Local source: phases/19-capstone-projects/58-vision-encoder-patches/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def patchify(image, patch_size):
    """image is a nonempty rectangular 2D scalar matrix; both dimensions must be divisible by exact positive int patch_size. Return flattened patches in row-major patch order, pixels within each patch row-major. Invalid shape or size raises ValueError."""
    raise NotImplementedError('TODO 1: patchify; see PROMPT.md')

def position_encoding(position, dimensions):
    """dimensions is exact positive even int and position is numeric >=0. Return sin(position/10000**(2*i/dimensions)) then cos of the same angle for i=0..dimensions/2-1, interleaved. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 2: position_encoding; see PROMPT.md')
