"""Original interview practice for 03-deep-learning-core/08-weight-initialization.

Local source: phases/03-deep-learning-core/08-weight-initialization/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def summary(values):
    """Return {'mean':arithmetic mean,'variance':population variance,'min':minimum,'max':maximum} for a nonempty numeric list. Empty input raises ValueError."""
    raise NotImplementedError('TODO 1: summary; see PROMPT.md')

def parameter_memory(shapes, bytes_per_parameter):
    """Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError."""
    raise NotImplementedError('TODO 2: parameter_memory; see PROMPT.md')
