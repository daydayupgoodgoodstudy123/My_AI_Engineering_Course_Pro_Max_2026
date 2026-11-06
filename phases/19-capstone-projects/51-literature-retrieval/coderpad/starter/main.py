"""Original interview practice for 19-capstone-projects/51-literature-retrieval.

Local source: phases/19-capstone-projects/51-literature-retrieval/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def rrf(rankings, constant=60):
    """For each ranking, score each id once at its FIRST 1-based rank using 1/(constant+rank). Sum across lists. Return ids sorted by descending total score, then lexicographic id. constant>=0 else ValueError; empty rankings yields []."""
    raise NotImplementedError('TODO 1: rrf; see PROMPT.md')

def unsupported_claims(claims, evidence_ids):
    """Claims have unique id(str) and references(list of evidence ids). Return sorted claim ids lacking references or containing any unknown reference. Duplicate claim ids raises ValueError. Having a reference verifies linkage only, not factual truth."""
    raise NotImplementedError('TODO 2: unsupported_claims; see PROMPT.md')
