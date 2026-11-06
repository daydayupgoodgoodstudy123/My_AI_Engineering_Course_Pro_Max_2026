"""Original interview practice for 06-speech-and-audio/10-audio-language-models.

Local source: phases/06-speech-and-audio/10-audio-language-models/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def audio_frames(samples, width, hop):
    """width and hop are exact positive ints. Return complete windows only, starting at 0,hop,2*hop...; drop incomplete tail. Short or empty signals yield []. Invalid size raises ValueError."""
    raise NotImplementedError('TODO 1: audio_frames; see PROMPT.md')

def attention(query, keys, values):
    """query is nonempty length d; keys is nonempty NxD and values is NxV with nonempty equal row widths. Compute softmax(query dot key / sqrt(d)) then the weighted sum of value rows. Invalid shapes raise ValueError; implement with Python lists."""
    raise NotImplementedError('TODO 2: attention; see PROMPT.md')
