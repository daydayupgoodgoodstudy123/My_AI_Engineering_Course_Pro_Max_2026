"""Original interview practice for 19-capstone-projects/58-vision-encoder-patches.

Local source: phases/19-capstone-projects/58-vision-encoder-patches/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def patchify(image, patch_size):
    if type(patch_size) is not int or patch_size <= 0 or (not image) or (not image[0]) or any((len(r) != len(image[0]) for r in image)) or len(image) % patch_size or len(image[0]) % patch_size:
        raise ValueError('patch shape')
    p = patch_size
    return [[image[r + i][c + j] for i in range(p) for j in range(p)] for r in range(0, len(image), p) for c in range(0, len(image[0]), p)]

def position_encoding(position, dimensions):
    if position < 0 or type(dimensions) is not int or dimensions <= 0 or dimensions % 2:
        raise ValueError('dimensions')
    result = []
    for i in range(dimensions // 2):
        angle = position / 10000 ** (2 * i / dimensions)
        result.extend([math.sin(angle), math.cos(angle)])
    return result
