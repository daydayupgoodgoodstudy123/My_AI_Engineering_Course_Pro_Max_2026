"""Original interview practice for 12-multimodal-ai/22-document-diagram-understanding.

Local source: phases/12-multimodal-ai/22-document-diagram-understanding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bio_spans(labels):
    """Labels are O, B-TYPE or I-TYPE with nonempty TYPE. Return {'type','start','end'} spans with half-open indices. I-TYPE without matching active type is treated as B-TYPE. Invalid label syntax raises ValueError. Consecutive B labels always start new entities."""
    raise NotImplementedError('TODO 1: bio_spans; see PROMPT.md')

def patchify(image, patch_size):
    """image is a nonempty rectangular 2D scalar matrix; both dimensions must be divisible by exact positive int patch_size. Return flattened patches in row-major patch order, pixels within each patch row-major. Invalid shape or size raises ValueError."""
    raise NotImplementedError('TODO 2: patchify; see PROMPT.md')
