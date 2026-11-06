"""Original interview practice for 19-capstone-projects/64-chunking-strategies-advanced.

Local source: phases/19-capstone-projects/64-chunking-strategies-advanced/docs/en.md (sha256 in SCOPE.json).
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

def select_context(items, budget):
    if type(budget) is not int or budget < 0 or any((type(x['tokens']) is not int or x['tokens'] < 0 for x in items)):
        raise ValueError('budget')
    result = []
    for item in sorted(items, key=lambda x: (-x['score'], x['id'])):
        if item['tokens'] <= budget:
            result.append(item['id'])
            budget -= item['tokens']
    return result
