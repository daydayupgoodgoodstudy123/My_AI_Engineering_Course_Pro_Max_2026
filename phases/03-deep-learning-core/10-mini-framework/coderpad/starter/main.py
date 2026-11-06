"""Original interview practice for 03-deep-learning-core/10-mini-framework.

Local source: phases/03-deep-learning-core/10-mini-framework/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def linear(features, weights, bias):
    """weights is a list of output rows, each matching len(features); bias length equals row count. Return dot(row,features)+bias per row. Invalid shapes raise ValueError. Empty output weights and bias yield []."""
    raise NotImplementedError('TODO 1: linear; see PROMPT.md')

def quadratic_gradient(weights, target):
    """For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 2: quadratic_gradient; see PROMPT.md')
