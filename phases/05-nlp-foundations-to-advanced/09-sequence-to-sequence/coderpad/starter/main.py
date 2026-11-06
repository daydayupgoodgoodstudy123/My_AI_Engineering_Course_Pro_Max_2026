"""Original interview practice for 05-nlp-foundations-to-advanced/09-sequence-to-sequence.

Local source: phases/05-nlp-foundations-to-advanced/09-sequence-to-sequence/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def lag_features(series, window):
    """window is exact positive int. Return {'x':[each consecutive window before target], 'y':[next value]}. Never include the target in its own features. window>=len(series) yields empty x/y. Invalid window raises ValueError."""
    raise NotImplementedError('TODO 1: lag_features; see PROMPT.md')

def masked_probabilities(logits, allowed):
    """allowed is a list of unique valid indices; return softmax over allowed logits with 0 at every disallowed index. Preserve original output length. Empty allowed, duplicate/out-of-range/non-int index, or empty logits raises ValueError. Use stable exponentiation."""
    raise NotImplementedError('TODO 2: masked_probabilities; see PROMPT.md')
