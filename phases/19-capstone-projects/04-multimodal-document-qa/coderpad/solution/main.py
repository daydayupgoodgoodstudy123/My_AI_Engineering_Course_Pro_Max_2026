"""Original interview practice for 19-capstone-projects/04-multimodal-document-qa.

Local source: phases/19-capstone-projects/04-multimodal-document-qa/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def patchify(image, patch_size):
    if type(patch_size) is not int or patch_size <= 0 or (not image) or (not image[0]) or any((len(r) != len(image[0]) for r in image)) or len(image) % patch_size or len(image[0]) % patch_size:
        raise ValueError('patch shape')
    p = patch_size
    return [[image[r + i][c + j] for i in range(p) for j in range(p)] for r in range(0, len(image), p) for c in range(0, len(image[0]), p)]

def token_f1(reference, answer):
    if not reference or not answer:
        return 1 if not reference and (not answer) else 0
    overlap = sum((Counter(reference) & Counter(answer)).values())
    p = overlap / len(answer)
    r = overlap / len(reference)
    return 2 * p * r / (p + r) if p + r else 0
