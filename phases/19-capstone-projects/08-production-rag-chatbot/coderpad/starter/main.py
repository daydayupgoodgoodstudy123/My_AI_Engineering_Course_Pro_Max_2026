"""Original interview practice for 19-capstone-projects/08-production-rag-chatbot.

Local source: phases/19-capstone-projects/08-production-rag-chatbot/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def rrf(rankings, constant=60):
    """For each ranking, score each id once at its FIRST 1-based rank using 1/(constant+rank). Sum across lists. Return ids sorted by descending total score, then lexicographic id. constant>=0 else ValueError; empty rankings yields []."""
    raise NotImplementedError('TODO 1: rrf; see PROMPT.md')

def select_context(items, budget):
    """items contain id(str), tokens(exact nonnegative int), score(number). Sort descending score with lexicographic id ties, then greedily accept each item that fits remaining exact nonnegative integer budget; skip oversize items and continue. Return selected ids in that order. Invalid costs/budget raise ValueError."""
    raise NotImplementedError('TODO 2: select_context; see PROMPT.md')
