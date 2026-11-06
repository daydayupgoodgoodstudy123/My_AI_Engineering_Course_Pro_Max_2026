"""Original interview practice for 12-multimodal-ai/09-qwen-vl-family-dynamic-fps.

Local source: phases/12-multimodal-ai/09-qwen-vl-family-dynamic-fps/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def sample_frames(length, count):
    """Require exact nonnegative integers length/count and count<=length. Return count indices spanning 0..length-1 using floor(i*(length-1)/(count-1)). count=0 -> []; count=1 -> [0]. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 1: sample_frames; see PROMPT.md')

def select_context(items, budget):
    """items contain id(str), tokens(exact nonnegative int), score(number). Sort descending score with lexicographic id ties, then greedily accept each item that fits remaining exact nonnegative integer budget; skip oversize items and continue. Return selected ids in that order. Invalid costs/budget raise ValueError."""
    raise NotImplementedError('TODO 2: select_context; see PROMPT.md')
