"""Original interview practice for 19-capstone-projects/31-tokenized-dataset-sliding-window.

Local source: phases/19-capstone-projects/31-tokenized-dataset-sliding-window/docs/en.md (sha256 in SCOPE.json).
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

def causal_mask(length, window=None):
    if type(length) is not int or length < 0 or (window is not None and (type(window) is not int or window <= 0)):
        raise ValueError('shape')
    return [[j <= i and (window is None or i - j < window) for j in range(length)] for i in range(length)]
