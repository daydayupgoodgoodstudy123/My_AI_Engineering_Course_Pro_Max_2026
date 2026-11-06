"""Original interview practice for 06-speech-and-audio/03-audio-classification.

Local source: phases/06-speech-and-audio/03-audio-classification/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def energy_vad(chunks, threshold):
    """For each numeric audio chunk, return RMS>=threshold; an empty chunk has RMS 0. threshold must be >=0 or raise ValueError. No model or microphone access."""
    raise NotImplementedError('TODO 1: energy_vad; see PROMPT.md')

def nearest(query, points, k):
    """Return indices of the k nearest points by squared Euclidean distance; ties use lower original index. All points must match query dimension. k is an exact int in [0,len(points)], otherwise ValueError. k=0 returns []."""
    raise NotImplementedError('TODO 2: nearest; see PROMPT.md')
