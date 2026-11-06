"""Original interview practice for 03-deep-learning-core/11-intro-to-pytorch.

Local source: phases/03-deep-learning-core/11-intro-to-pytorch/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def parameter_memory(shapes, bytes_per_parameter):
    """Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError."""
    raise NotImplementedError('TODO 1: parameter_memory; see PROMPT.md')

def make_batches(items, maximum):
    """items are {'id','tokens':exact positive int}; maximum exact positive int. Preserve input order, greedily pack consecutive items while sum tokens<=maximum. Oversized item raises ValueError rather than silently dropping it. Return list of lists of ids; empty input yields []."""
    raise NotImplementedError('TODO 2: make_batches; see PROMPT.md')
