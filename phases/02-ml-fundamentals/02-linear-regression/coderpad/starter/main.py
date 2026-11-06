"""Original interview practice for 02-ml-fundamentals/02-linear-regression.

Local source: phases/02-ml-fundamentals/02-linear-regression/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def linear(features, weights, bias):
    """weights is a list of output rows, each matching len(features); bias length equals row count. Return dot(row,features)+bias per row. Invalid shapes raise ValueError. Empty output weights and bias yield []."""
    raise NotImplementedError('TODO 1: linear; see PROMPT.md')

def mse(predicted, expected):
    """Return mean squared error of equal-length nonempty numeric lists. Unequal lengths or empty inputs raise ValueError."""
    raise NotImplementedError('TODO 2: mse; see PROMPT.md')
