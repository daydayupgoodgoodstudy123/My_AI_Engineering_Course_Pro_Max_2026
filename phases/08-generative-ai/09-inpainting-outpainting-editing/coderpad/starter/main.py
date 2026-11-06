"""Original interview practice for 08-generative-ai/09-inpainting-outpainting-editing.

Local source: phases/08-generative-ai/09-inpainting-outpainting-editing/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def rle_encode(values):
    """Return consecutive [value,count] runs for a list of exact booleans. Empty list returns []; reject non-bool elements with ValueError. Preserve runs and original order."""
    raise NotImplementedError('TODO 1: rle_encode; see PROMPT.md')

def diffuse(clean, noise, alpha_bar):
    """For equal-length vectors and alpha_bar in [0,1], return sqrt(alpha_bar)*clean + sqrt(1-alpha_bar)*noise. Invalid coefficient or unequal lengths raises ValueError. Empty vectors are valid; noise is injected, no RNG."""
    raise NotImplementedError('TODO 2: diffuse; see PROMPT.md')
