"""Original interview practice for 12-multimodal-ai/06-any-resolution-patch-n-pack.

Local source: phases/12-multimodal-ai/06-any-resolution-patch-n-pack/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def patchify(image, patch_size):
    """image is a nonempty rectangular 2D scalar matrix; both dimensions must be divisible by exact positive int patch_size. Return flattened patches in row-major patch order, pixels within each patch row-major. Invalid shape or size raises ValueError."""
    raise NotImplementedError('TODO 1: patchify; see PROMPT.md')

def make_batches(items, maximum):
    """items are {'id','tokens':exact positive int}; maximum exact positive int. Preserve input order, greedily pack consecutive items while sum tokens<=maximum. Oversized item raises ValueError rather than silently dropping it. Return list of lists of ids; empty input yields []."""
    raise NotImplementedError('TODO 2: make_batches; see PROMPT.md')
