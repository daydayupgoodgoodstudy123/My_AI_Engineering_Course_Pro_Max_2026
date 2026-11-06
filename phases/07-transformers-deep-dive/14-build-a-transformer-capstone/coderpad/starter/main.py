"""Original interview practice for 07-transformers-deep-dive/14-build-a-transformer-capstone.

Local source: phases/07-transformers-deep-dive/14-build-a-transformer-capstone/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def causal_mask(length, window=None):
    """Return length x length booleans where row i may attend column j iff j<=i and, if window provided, i-j<window. length exact int >=0; window None or exact positive int. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: causal_mask; see PROMPT.md')

def parameter_memory(shapes, bytes_per_parameter):
    """Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError."""
    raise NotImplementedError('TODO 2: parameter_memory; see PROMPT.md')
