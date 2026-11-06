"""Original interview practice for 19-capstone-projects/51-literature-retrieval.

Local source: phases/19-capstone-projects/51-literature-retrieval/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def rrf(rankings, constant=60):
    if constant < 0:
        raise ValueError('constant')
    scores = {}
    for ranking in rankings:
        seen = set()
        for rank, item in enumerate(ranking, 1):
            if item not in seen:
                scores[item] = scores.get(item, 0) + 1 / (constant + rank)
                seen.add(item)
    return sorted(scores, key=lambda x: (-scores[x], x))

def unsupported_claims(claims, evidence_ids):
    if len({c['id'] for c in claims}) != len(claims):
        raise ValueError('duplicate claim')
    known = set(evidence_ids)
    return sorted((c['id'] for c in claims if not c['references'] or not set(c['references']) <= known))
