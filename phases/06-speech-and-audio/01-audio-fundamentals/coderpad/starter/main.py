"""Original interview practice for 06-speech-and-audio/01-audio-fundamentals.

Local source: phases/06-speech-and-audio/01-audio-fundamentals/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def dft(samples):
    """Compute unnormalized forward DFT of real samples using exp(-2*pi*i*k*n/N). Return one [real,imaginary] pair per frequency bin. Empty input returns []. No FFT library."""
    raise NotImplementedError('TODO 1: dft; see PROMPT.md')

def energy_vad(chunks, threshold):
    """For each numeric audio chunk, return RMS>=threshold; an empty chunk has RMS 0. threshold must be >=0 or raise ValueError. No model or microphone access."""
    raise NotImplementedError('TODO 2: energy_vad; see PROMPT.md')
