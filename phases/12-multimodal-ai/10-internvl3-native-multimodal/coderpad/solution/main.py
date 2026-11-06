"""Original interview practice for 12-multimodal-ai/10-internvl3-native-multimodal.

Local source: phases/12-multimodal-ai/10-internvl3-native-multimodal/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def patchify(image, patch_size):
    if type(patch_size) is not int or patch_size <= 0 or (not image) or (not image[0]) or any((len(r) != len(image[0]) for r in image)) or len(image) % patch_size or len(image[0]) % patch_size:
        raise ValueError('patch shape')
    p = patch_size
    return [[image[r + i][c + j] for i in range(p) for j in range(p)] for r in range(0, len(image), p) for c in range(0, len(image[0]), p)]

def parameter_memory(shapes, bytes_per_parameter):
    if type(bytes_per_parameter) is not int or bytes_per_parameter <= 0 or any((type(d) is not int or d <= 0 for shape in shapes for d in shape)):
        raise ValueError('shape')
    return sum((math.prod(shape) for shape in shapes)) * bytes_per_parameter
