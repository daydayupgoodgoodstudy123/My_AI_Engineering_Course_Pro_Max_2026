"""Original interview practice for 08-generative-ai/07-latent-diffusion-stable-diffusion.

Local source: phases/08-generative-ai/07-latent-diffusion-stable-diffusion/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def diffuse(clean, noise, alpha_bar):
    """For equal-length vectors and alpha_bar in [0,1], return sqrt(alpha_bar)*clean + sqrt(1-alpha_bar)*noise. Invalid coefficient or unequal lengths raises ValueError. Empty vectors are valid; noise is injected, no RNG."""
    raise NotImplementedError('TODO 1: diffuse; see PROMPT.md')

def quantize(values, bits):
    """bits must be exact int 2..8. Set bound=2**(bits-1)-1, scale=max(abs(values))/bound (or 1 for empty/all-zero input). Return {'values':[rounded x/scale clipped to -bound..bound], 'scale':scale}. Python round (ties to even) defines rounding."""
    raise NotImplementedError('TODO 2: quantize; see PROMPT.md')
