"""Original interview practice for 12-multimodal-ai/08-llava-onevision-single-multi-video.

Local source: phases/12-multimodal-ai/08-llava-onevision-single-multi-video/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def sample_frames(length, count):
    if type(length) is not int or type(count) is not int or (not 0 <= count <= length):
        raise ValueError('frames')
    if count == 0:
        return []
    if count == 1:
        return [0]
    return [i * (length - 1) // (count - 1) for i in range(count)]

def patchify(image, patch_size):
    if type(patch_size) is not int or patch_size <= 0 or (not image) or (not image[0]) or any((len(r) != len(image[0]) for r in image)) or len(image) % patch_size or len(image[0]) % patch_size:
        raise ValueError('patch shape')
    p = patch_size
    return [[image[r + i][c + j] for i in range(p) for j in range(p)] for r in range(0, len(image), p) for c in range(0, len(image[0]), p)]
