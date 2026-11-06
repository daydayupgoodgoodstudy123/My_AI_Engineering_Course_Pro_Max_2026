"""Original interview practice for 12-multimodal-ai/23-colpali-vision-native-rag.

Local source: phases/12-multimodal-ai/23-colpali-vision-native-rag/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def cosine(a, b):
    if len(a) != len(b):
        raise ValueError('shape')
    den = math.sqrt(sum((x * x for x in a)) * sum((y * y for y in b)))
    return sum((x * y for x, y in zip(a, b))) / den if den else 0

def retrieval_metrics(ranked, relevant, k):
    if type(k) is not int or k <= 0 or len(set(ranked)) != len(ranked):
        raise ValueError('ranking')
    rel = set(relevant)
    top = ranked[:k]
    hits = sum((x in rel for x in top))
    first = next((i for i, x in enumerate(top, 1) if x in rel), None)
    return {'precision': hits / k, 'recall': hits / len(rel) if rel else 0, 'reciprocal_rank': 1 / first if first else 0}
