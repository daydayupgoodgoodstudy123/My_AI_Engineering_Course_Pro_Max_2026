"""Original interview practice for 06-speech-and-audio/07-text-to-speech.

Local source: phases/06-speech-and-audio/07-text-to-speech/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def lag_features(series, window):
    if type(window) is not int or window <= 0:
        raise ValueError('window')
    return {'x': [series[i - window:i] for i in range(window, len(series))], 'y': series[window:]}

def learning_rate(step, total, warmup, peak):
    if any((type(x) is not int for x in (step, total, warmup))) or total <= 0 or (not 0 <= warmup < total) or (step < 0) or (peak < 0):
        raise ValueError('schedule')
    if step < warmup:
        return peak * step / warmup
    return peak * (1 + math.cos(math.pi * min(1, (step - warmup) / (total - warmup)))) / 2
