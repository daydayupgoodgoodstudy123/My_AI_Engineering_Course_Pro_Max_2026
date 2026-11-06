"""Original interview practice for 04-computer-vision/23-diffusion-transformers-rectified-flow.

Local source: phases/04-computer-vision/23-diffusion-transformers-rectified-flow/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def flow_step(state, velocity, delta):
    """Return state+delta*velocity coordinatewise. Require equal lengths and numeric delta in [0,1]; otherwise ValueError. Empty vectors are valid."""
    raise NotImplementedError('TODO 1: flow_step; see PROMPT.md')

def diffuse(clean, noise, alpha_bar):
    """For equal-length vectors and alpha_bar in [0,1], return sqrt(alpha_bar)*clean + sqrt(1-alpha_bar)*noise. Invalid coefficient or unequal lengths raises ValueError. Empty vectors are valid; noise is injected, no RNG."""
    raise NotImplementedError('TODO 2: diffuse; see PROMPT.md')
