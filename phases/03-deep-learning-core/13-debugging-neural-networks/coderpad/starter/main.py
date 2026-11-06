"""Original interview practice for 03-deep-learning-core/13-debugging-neural-networks.

Local source: phases/03-deep-learning-core/13-debugging-neural-networks/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def clip_gradients(gradients, maximum):
    """Return gradients scaled together so L2 norm is at most maximum; leave already-small vectors unchanged in value. maximum>=0, otherwise ValueError. Zero and empty vectors are valid."""
    raise NotImplementedError('TODO 1: clip_gradients; see PROMPT.md')

def zscore_flags(values, threshold):
    """Use population mean/variance from values; flag abs(z)>threshold (strict). Constant or empty lists yield all False/empty. Negative threshold raises ValueError."""
    raise NotImplementedError('TODO 2: zscore_flags; see PROMPT.md')
