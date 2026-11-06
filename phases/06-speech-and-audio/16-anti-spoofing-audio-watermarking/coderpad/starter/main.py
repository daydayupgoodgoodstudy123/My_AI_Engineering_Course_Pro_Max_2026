"""Original interview practice for 06-speech-and-audio/16-anti-spoofing-audio-watermarking.

Local source: phases/06-speech-and-audio/16-anti-spoofing-audio-watermarking/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bit_accuracy(expected, observed):
    """Require equal-length nonempty lists of exact integer bits 0 or 1 (bool invalid). Return fraction matching. Invalid lists raise ValueError. This bit check does not establish provenance authenticity."""
    raise NotImplementedError('TODO 1: bit_accuracy; see PROMPT.md')

def classification(expected, predicted):
    """Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError."""
    raise NotImplementedError('TODO 2: classification; see PROMPT.md')
