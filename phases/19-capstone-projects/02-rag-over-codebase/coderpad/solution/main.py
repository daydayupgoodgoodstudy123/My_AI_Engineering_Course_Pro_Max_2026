"""Original interview practice for 19-capstone-projects/02-rag-over-codebase.

Local source: phases/19-capstone-projects/02-rag-over-codebase/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def chunk_tokens(tokens, size, overlap):
    if type(size) is not int or type(overlap) is not int or size <= 0 or (not 0 <= overlap < size):
        raise ValueError('window')
    result = []
    start = 0
    while start < len(tokens):
        result.append(tokens[start:start + size])
        if start + size >= len(tokens):
            break
        start += size - overlap
    return result

def retrieval_metrics(ranked, relevant, k):
    if type(k) is not int or k <= 0 or len(set(ranked)) != len(ranked):
        raise ValueError('ranking')
    rel = set(relevant)
    top = ranked[:k]
    hits = sum((x in rel for x in top))
    first = next((i for i, x in enumerate(top, 1) if x in rel), None)
    return {'precision': hits / k, 'recall': hits / len(rel) if rel else 0, 'reciprocal_rank': 1 / first if first else 0}
