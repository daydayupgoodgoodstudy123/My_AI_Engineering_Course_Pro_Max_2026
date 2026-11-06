"""Original interview practice for 10-llms-from-scratch/18-multi-token-prediction.

Local source: phases/10-llms-from-scratch/18-multi-token-prediction/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def lag_features(series, window):
    if type(window) is not int or window <= 0:
        raise ValueError('window')
    return {'x': [series[i - window:i] for i in range(window, len(series))], 'y': series[window:]}

def causal_mask(length, window=None):
    if type(length) is not int or length < 0 or (window is not None and (type(window) is not int or window <= 0)):
        raise ValueError('shape')
    return [[j <= i and (window is None or i - j < window) for j in range(length)] for i in range(length)]
