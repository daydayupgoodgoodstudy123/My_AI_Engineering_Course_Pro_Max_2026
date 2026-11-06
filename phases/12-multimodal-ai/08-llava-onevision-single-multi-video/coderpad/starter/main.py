"""Original interview practice for 12-multimodal-ai/08-llava-onevision-single-multi-video.

Local source: phases/12-multimodal-ai/08-llava-onevision-single-multi-video/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def sample_frames(length, count):
    """Require exact nonnegative integers length/count and count<=length. Return count indices spanning 0..length-1 using floor(i*(length-1)/(count-1)). count=0 -> []; count=1 -> [0]. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 1: sample_frames; see PROMPT.md')

def patchify(image, patch_size):
    """image is a nonempty rectangular 2D scalar matrix; both dimensions must be divisible by exact positive int patch_size. Return flattened patches in row-major patch order, pixels within each patch row-major. Invalid shape or size raises ValueError."""
    raise NotImplementedError('TODO 2: patchify; see PROMPT.md')
