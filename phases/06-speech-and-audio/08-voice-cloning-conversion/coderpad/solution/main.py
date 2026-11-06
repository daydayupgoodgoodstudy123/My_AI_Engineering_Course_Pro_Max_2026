"""Original interview practice for 06-speech-and-audio/08-voice-cloning-conversion.

Local source: phases/06-speech-and-audio/08-voice-cloning-conversion/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def cosine(a, b):
    if len(a) != len(b):
        raise ValueError('shape')
    den = math.sqrt(sum((x * x for x in a)) * sum((y * y for y in b)))
    return sum((x * y for x, y in zip(a, b))) / den if den else 0

def bit_accuracy(expected, observed):
    if not expected or len(expected) != len(observed) or any((type(x) is not int or x not in (0, 1) for x in expected + observed)):
        raise ValueError('bits')
    return sum((a == b for a, b in zip(expected, observed))) / len(expected)
