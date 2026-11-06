"""Original interview practice for 19-capstone-projects/32-token-positional-embeddings.

Local source: phases/19-capstone-projects/32-token-positional-embeddings/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def position_encoding(position, dimensions):
    """dimensions is exact positive even int and position is numeric >=0. Return sin(position/10000**(2*i/dimensions)) then cos of the same angle for i=0..dimensions/2-1, interleaved. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: position_encoding; see PROMPT.md')

def linear(features, weights, bias):
    """weights is a list of output rows, each matching len(features); bias length equals row count. Return dot(row,features)+bias per row. Invalid shapes raise ValueError. Empty output weights and bias yield []."""
    raise NotImplementedError('TODO 2: linear; see PROMPT.md')
