"""Original interview practice for 19-capstone-projects/02-rag-over-codebase.

Local source: phases/19-capstone-projects/02-rag-over-codebase/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def chunk_tokens(tokens, size, overlap):
    """Require exact integers size>0 and 0<=overlap<size. Return windows starting at 0 then advancing size-overlap; include a short final window, stop once a window reaches the end. Empty tokens yields []. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: chunk_tokens; see PROMPT.md')

def retrieval_metrics(ranked, relevant, k):
    """ranked is a unique document-id list; relevant is a list treated as a set. k exact positive int. Return precision=len(top-k relevant)/k, recall=hits/number of unique relevant (0 if none), reciprocal_rank=1/first relevant rank within top-k (0 if none). Duplicate ranked ids or invalid k raises ValueError."""
    raise NotImplementedError('TODO 2: retrieval_metrics; see PROMPT.md')
