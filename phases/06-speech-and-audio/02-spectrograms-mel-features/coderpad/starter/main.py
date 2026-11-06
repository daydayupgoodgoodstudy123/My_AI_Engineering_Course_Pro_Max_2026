"""Original interview practice for 06-speech-and-audio/02-spectrograms-mel-features.

Local source: phases/06-speech-and-audio/02-spectrograms-mel-features/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def audio_frames(samples, width, hop):
    """width and hop are exact positive ints. Return complete windows only, starting at 0,hop,2*hop...; drop incomplete tail. Short or empty signals yield []. Invalid size raises ValueError."""
    raise NotImplementedError('TODO 1: audio_frames; see PROMPT.md')

def hz_to_mel(frequencies):
    """Return 2595*log10(1+f/700) per nonnegative frequency. Any negative frequency raises ValueError; empty input yields []."""
    raise NotImplementedError('TODO 2: hz_to_mel; see PROMPT.md')
