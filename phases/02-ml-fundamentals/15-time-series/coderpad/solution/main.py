"""Original interview practice for 02-ml-fundamentals/15-time-series.

Local source: phases/02-ml-fundamentals/15-time-series/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def lag_features(series, window):
    if type(window) is not int or window <= 0:
        raise ValueError('window')
    return {'x': [series[i - window:i] for i in range(window, len(series))], 'y': series[window:]}

def mse(predicted, expected):
    if not predicted or len(predicted) != len(expected):
        raise ValueError('shape')
    return sum(((a - b) ** 2 for a, b in zip(predicted, expected))) / len(predicted)
