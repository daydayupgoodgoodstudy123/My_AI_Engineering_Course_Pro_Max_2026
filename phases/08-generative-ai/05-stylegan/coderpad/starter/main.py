"""Original interview practice for 08-generative-ai/05-stylegan.

Local source: phases/08-generative-ai/05-stylegan/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def summary(values):
    """Return {'mean':arithmetic mean,'variance':population variance,'min':minimum,'max':maximum} for a nonempty numeric list. Empty input raises ValueError."""
    raise NotImplementedError('TODO 1: summary; see PROMPT.md')

def linear(features, weights, bias):
    """weights is a list of output rows, each matching len(features); bias length equals row count. Return dot(row,features)+bias per row. Invalid shapes raise ValueError. Empty output weights and bias yield []."""
    raise NotImplementedError('TODO 2: linear; see PROMPT.md')
