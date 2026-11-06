"""Original interview practice for 06-speech-and-audio/02-spectrograms-mel-features.

Local source: phases/06-speech-and-audio/02-spectrograms-mel-features/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def audio_frames(samples, width, hop):
    if any((type(x) is not int or x <= 0 for x in (width, hop))):
        raise ValueError('window')
    return [samples[i:i + width] for i in range(0, len(samples) - width + 1, hop)]

def hz_to_mel(frequencies):
    if any((f < 0 for f in frequencies)):
        raise ValueError('frequency')
    return [2595 * math.log10(1 + f / 700) for f in frequencies]
