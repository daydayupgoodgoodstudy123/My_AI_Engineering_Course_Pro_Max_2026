"""Original interview practice for 05-nlp-foundations-to-advanced/09-sequence-to-sequence.

Local source: phases/05-nlp-foundations-to-advanced/09-sequence-to-sequence/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def lag_features(series, window):
    if type(window) is not int or window <= 0:
        raise ValueError('window')
    return {'x': [series[i - window:i] for i in range(window, len(series))], 'y': series[window:]}

def masked_probabilities(logits, allowed):
    if not logits or not allowed or any((type(i) is not int or not 0 <= i < len(logits) for i in allowed)) or (len(set(allowed)) != len(allowed)):
        raise ValueError('mask')
    maximum = max((logits[i] for i in allowed))
    weights = {i: math.exp(logits[i] - maximum) for i in allowed}
    total = sum(weights.values())
    return [weights.get(i, 0) / total for i in range(len(logits))]
