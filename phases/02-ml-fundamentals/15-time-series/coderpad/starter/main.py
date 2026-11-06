"""Original interview practice for 02-ml-fundamentals/15-time-series.

Local source: phases/02-ml-fundamentals/15-time-series/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def lag_features(series, window):
    """window is exact positive int. Return {'x':[each consecutive window before target], 'y':[next value]}. Never include the target in its own features. window>=len(series) yields empty x/y. Invalid window raises ValueError."""
    raise NotImplementedError('TODO 1: lag_features; see PROMPT.md')

def mse(predicted, expected):
    """Return mean squared error of equal-length nonempty numeric lists. Unequal lengths or empty inputs raise ValueError."""
    raise NotImplementedError('TODO 2: mse; see PROMPT.md')
