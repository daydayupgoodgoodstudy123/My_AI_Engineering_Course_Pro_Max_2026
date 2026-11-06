"""Original interview practice for 05-nlp-foundations-to-advanced/07-pos-tagging-parsing.

Local source: phases/05-nlp-foundations-to-advanced/07-pos-tagging-parsing/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def markov_step(distribution, transition):
    """Distribution is a nonempty probability row vector; transition is an NxN row-stochastic matrix. Reject wrong shapes, negatives or row/distribution sums outside 1e-9 with ValueError. Return distribution @ transition."""
    raise NotImplementedError('TODO 1: markov_step; see PROMPT.md')

def top_k(scores, k):
    """Return the indices of k largest scores, descending score with lower original index ties. k exact int in [0,len(scores)], else ValueError; k=0 returns []."""
    raise NotImplementedError('TODO 2: top_k; see PROMPT.md')
