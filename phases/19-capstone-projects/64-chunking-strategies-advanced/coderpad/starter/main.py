"""Original interview practice for 19-capstone-projects/64-chunking-strategies-advanced.

Local source: phases/19-capstone-projects/64-chunking-strategies-advanced/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def chunk_tokens(tokens, size, overlap):
    """Require exact integers size>0 and 0<=overlap<size. Return windows starting at 0 then advancing size-overlap; include a short final window, stop once a window reaches the end. Empty tokens yields []. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: chunk_tokens; see PROMPT.md')

def select_context(items, budget):
    """items contain id(str), tokens(exact nonnegative int), score(number). Sort descending score with lexicographic id ties, then greedily accept each item that fits remaining exact nonnegative integer budget; skip oversize items and continue. Return selected ids in that order. Invalid costs/budget raise ValueError."""
    raise NotImplementedError('TODO 2: select_context; see PROMPT.md')
