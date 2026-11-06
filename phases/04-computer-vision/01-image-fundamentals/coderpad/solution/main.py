"""Original interview practice for 04-computer-vision/01-image-fundamentals.

Local source: phases/04-computer-vision/01-image-fundamentals/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def transpose(rows):
    if not rows:
        return []
    if any((len(r) != len(rows[0]) for r in rows)):
        raise ValueError('ragged')
    return [list(c) for c in zip(*rows)]

def standardize(train, values):
    if not train:
        raise ValueError('empty train')
    mean = sum(train) / len(train)
    scale = math.sqrt(sum(((x - mean) ** 2 for x in train)) / len(train)) or 1
    return {'mean': mean, 'scale': scale, 'values': [(x - mean) / scale for x in values]}
