"""Original interview practice for 19-capstone-projects/67-query-rewriting-hyde.

Local source: phases/19-capstone-projects/67-query-rewriting-hyde/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def bag_of_words(tokens, vocabulary):
    if len(set(vocabulary)) != len(vocabulary):
        raise ValueError('duplicate vocabulary')
    counts = Counter(tokens)
    return [counts[t] for t in vocabulary]

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
