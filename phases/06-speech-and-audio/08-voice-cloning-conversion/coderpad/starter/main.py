"""Original interview practice for 06-speech-and-audio/08-voice-cloning-conversion.

Local source: phases/06-speech-and-audio/08-voice-cloning-conversion/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def cosine(a, b):
    """Return cosine similarity of equal-length numeric vectors. Define zero-norm or empty-vector similarity as 0. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 1: cosine; see PROMPT.md')

def bit_accuracy(expected, observed):
    """Require equal-length nonempty lists of exact integer bits 0 or 1 (bool invalid). Return fraction matching. Invalid lists raise ValueError. This bit check does not establish provenance authenticity."""
    raise NotImplementedError('TODO 2: bit_accuracy; see PROMPT.md')
