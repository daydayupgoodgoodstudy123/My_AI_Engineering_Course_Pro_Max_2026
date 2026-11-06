"""Original interview practice for 03-deep-learning-core/02-multi-layer-networks.

Local source: phases/03-deep-learning-core/02-multi-layer-networks/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def linear(features, weights, bias):
    """weights is a list of output rows, each matching len(features); bias length equals row count. Return dot(row,features)+bias per row. Invalid shapes raise ValueError. Empty output weights and bias yield []."""
    raise NotImplementedError('TODO 1: linear; see PROMPT.md')

def matmul(a, b):
    """Multiply nonempty rectangular numeric matrices using row-by-column products. Reject empty matrices, ragged rows, empty rows or incompatible inner dimensions with ValueError."""
    raise NotImplementedError('TODO 2: matmul; see PROMPT.md')
