"""Original interview practice for 20-recursive-self-improvement/16-model-collapse-and-diversity.

Local source: phases/20-recursive-self-improvement/16-model-collapse-and-diversity/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def entropy(probabilities):
    """Return Shannon entropy in bits. Require a nonempty list of numeric probabilities in [0,1] summing to 1 within 1e-9, else ValueError. Define 0*log2(0)=0."""
    raise NotImplementedError('TODO 1: entropy; see PROMPT.md')

def inverse_cdf(probabilities, uniforms):
    """Probabilities must be nonempty, nonnegative, sum to 1 within 1e-9. Each uniform is in [0,1). Return the first index whose cumulative probability is strictly greater than u. Invalid input raises ValueError; empty uniforms returns []. No RNG is called."""
    raise NotImplementedError('TODO 2: inverse_cdf; see PROMPT.md')
