"""Original interview practice for 19-capstone-projects/49-lm-eval-harness.

Local source: phases/19-capstone-projects/49-lm-eval-harness/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def perplexity(probabilities):
    """Return exp(-mean(log(p))) for nonempty true-token probabilities, each 0<p<=1. Invalid inputs raise ValueError. Probabilities are not required to sum to 1 because each refers to a different timestep."""
    raise NotImplementedError('TODO 1: perplexity; see PROMPT.md')

def retrieval_metrics(ranked, relevant, k):
    """ranked is a unique document-id list; relevant is a list treated as a set. k exact positive int. Return precision=len(top-k relevant)/k, recall=hits/number of unique relevant (0 if none), reciprocal_rank=1/first relevant rank within top-k (0 if none). Duplicate ranked ids or invalid k raises ValueError."""
    raise NotImplementedError('TODO 2: retrieval_metrics; see PROMPT.md')
