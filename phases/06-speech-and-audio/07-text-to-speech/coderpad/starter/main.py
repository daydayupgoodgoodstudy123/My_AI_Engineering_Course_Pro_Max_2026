"""Original interview practice for 06-speech-and-audio/07-text-to-speech.

Local source: phases/06-speech-and-audio/07-text-to-speech/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def lag_features(series, window):
    """window is exact positive int. Return {'x':[each consecutive window before target], 'y':[next value]}. Never include the target in its own features. window>=len(series) yields empty x/y. Invalid window raises ValueError."""
    raise NotImplementedError('TODO 1: lag_features; see PROMPT.md')

def learning_rate(step, total, warmup, peak):
    """Require exact integer total>0, 0<=warmup<total, step>=0, and peak>=0. If step<warmup return peak*step/warmup; otherwise peak*(1+cos(pi*min(1,(step-warmup)/(total-warmup))))/2. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 2: learning_rate; see PROMPT.md')
