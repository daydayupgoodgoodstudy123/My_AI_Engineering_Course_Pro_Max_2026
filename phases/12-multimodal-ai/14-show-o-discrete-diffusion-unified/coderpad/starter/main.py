"""Original interview practice for 12-multimodal-ai/14-show-o-discrete-diffusion-unified.

Local source: phases/12-multimodal-ai/14-show-o-discrete-diffusion-unified/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def masked_probabilities(logits, allowed):
    """allowed is a list of unique valid indices; return softmax over allowed logits with 0 at every disallowed index. Preserve original output length. Empty allowed, duplicate/out-of-range/non-int index, or empty logits raises ValueError. Use stable exponentiation."""
    raise NotImplementedError('TODO 1: masked_probabilities; see PROMPT.md')

def diffuse(clean, noise, alpha_bar):
    """For equal-length vectors and alpha_bar in [0,1], return sqrt(alpha_bar)*clean + sqrt(1-alpha_bar)*noise. Invalid coefficient or unequal lengths raises ValueError. Empty vectors are valid; noise is injected, no RNG."""
    raise NotImplementedError('TODO 2: diffuse; see PROMPT.md')
