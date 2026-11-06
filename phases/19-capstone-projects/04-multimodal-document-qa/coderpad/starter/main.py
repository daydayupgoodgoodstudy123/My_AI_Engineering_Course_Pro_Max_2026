"""Original interview practice for 19-capstone-projects/04-multimodal-document-qa.

Local source: phases/19-capstone-projects/04-multimodal-document-qa/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def patchify(image, patch_size):
    """image is a nonempty rectangular 2D scalar matrix; both dimensions must be divisible by exact positive int patch_size. Return flattened patches in row-major patch order, pixels within each patch row-major. Invalid shape or size raises ValueError."""
    raise NotImplementedError('TODO 1: patchify; see PROMPT.md')

def token_f1(reference, answer):
    """Inputs are token lists; count overlap as multiset intersection. Both empty ->1; exactly one empty ->0. Otherwise return harmonic mean of overlap/len(answer) and overlap/len(reference)."""
    raise NotImplementedError('TODO 2: token_f1; see PROMPT.md')
