"""Original interview practice for 01-math-foundations/20-fourier-transform.

Local source: phases/01-math-foundations/20-fourier-transform/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dft(samples):
    """Compute unnormalized forward DFT of real samples using exp(-2*pi*i*k*n/N). Return one [real,imaginary] pair per frequency bin. Empty input returns []. No FFT library."""
    raise NotImplementedError('TODO 1: dft; see PROMPT.md')

def audio_frames(samples, width, hop):
    """width and hop are exact positive ints. Return complete windows only, starting at 0,hop,2*hop...; drop incomplete tail. Short or empty signals yield []. Invalid size raises ValueError."""
    raise NotImplementedError('TODO 2: audio_frames; see PROMPT.md')
