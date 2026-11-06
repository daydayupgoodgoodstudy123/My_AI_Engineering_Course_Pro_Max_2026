"""Original interview practice for 10-llms-from-scratch/18-multi-token-prediction.

Local source: phases/10-llms-from-scratch/18-multi-token-prediction/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def lag_features(series, window):
    """window is exact positive int. Return {'x':[each consecutive window before target], 'y':[next value]}. Never include the target in its own features. window>=len(series) yields empty x/y. Invalid window raises ValueError."""
    raise NotImplementedError('TODO 1: lag_features; see PROMPT.md')

def causal_mask(length, window=None):
    """Return length x length booleans where row i may attend column j iff j<=i and, if window provided, i-j<window. length exact int >=0; window None or exact positive int. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 2: causal_mask; see PROMPT.md')
