"""Original interview practice for 06-speech-and-audio/06-speaker-recognition-verification.

Local source: phases/06-speech-and-audio/06-speaker-recognition-verification/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def cosine(a, b):
    if len(a) != len(b):
        raise ValueError('shape')
    den = math.sqrt(sum((x * x for x in a)) * sum((y * y for y in b)))
    return sum((x * y for x, y in zip(a, b))) / den if den else 0

def calibration_error(confidences, correct, bins):
    if not confidences or len(confidences) != len(correct) or type(bins) is not int or (bins <= 0) or any((not 0 <= p <= 1 for p in confidences)) or any((type(x) is not bool for x in correct)):
        raise ValueError('calibration')
    groups = {}
    for p, c in zip(confidences, correct):
        groups.setdefault(min(bins - 1, int(p * bins)), []).append((p, c))
    return sum((abs(sum((p for p, c in group)) - sum((c for p, c in group))) / len(confidences) for group in groups.values()))
