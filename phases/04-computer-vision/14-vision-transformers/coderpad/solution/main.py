"""Original interview practice for 04-computer-vision/14-vision-transformers.

Local source: phases/04-computer-vision/14-vision-transformers/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def patchify(image, patch_size):
    if type(patch_size) is not int or patch_size <= 0 or (not image) or (not image[0]) or any((len(r) != len(image[0]) for r in image)) or len(image) % patch_size or len(image[0]) % patch_size:
        raise ValueError('patch shape')
    p = patch_size
    return [[image[r + i][c + j] for i in range(p) for j in range(p)] for r in range(0, len(image), p) for c in range(0, len(image[0]), p)]

def attention(query, keys, values):
    if not query or not keys or len(keys) != len(values) or any((len(k) != len(query) for k in keys)) or (not values[0]) or any((len(v) != len(values[0]) for v in values)):
        raise ValueError('shape')
    scores = [sum((a * b for a, b in zip(query, k))) / math.sqrt(len(query)) for k in keys]
    maximum = max(scores)
    weights = [math.exp(s - maximum) for s in scores]
    total = sum(weights)
    return [sum((w * v[j] for w, v in zip(weights, values))) / total for j in range(len(values[0]))]
