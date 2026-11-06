"""Original interview practice for 12-multimodal-ai/06-any-resolution-patch-n-pack.

Local source: phases/12-multimodal-ai/06-any-resolution-patch-n-pack/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def patchify(image, patch_size):
    if type(patch_size) is not int or patch_size <= 0 or (not image) or (not image[0]) or any((len(r) != len(image[0]) for r in image)) or len(image) % patch_size or len(image[0]) % patch_size:
        raise ValueError('patch shape')
    p = patch_size
    return [[image[r + i][c + j] for i in range(p) for j in range(p)] for r in range(0, len(image), p) for c in range(0, len(image[0]), p)]

def make_batches(items, maximum):
    if type(maximum) is not int or maximum <= 0 or any((type(x['tokens']) is not int or not 0 < x['tokens'] <= maximum for x in items)):
        raise ValueError('batch')
    result = []
    current = []
    size = 0
    for x in items:
        if size + x['tokens'] > maximum:
            result.append(current)
            current = []
            size = 0
        current.append(x['id'])
        size += x['tokens']
    if current:
        result.append(current)
    return result
