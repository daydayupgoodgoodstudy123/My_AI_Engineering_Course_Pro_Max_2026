"""Original interview practice for 04-computer-vision/19-ocr-document-understanding.

Local source: phases/04-computer-vision/19-ocr-document-understanding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def ctc_decode(tokens, blank=0):
    result = []
    previous = object()
    for token in tokens:
        if token != previous and token != blank:
            result.append(token)
        previous = token
    return result

def edit_distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, a in enumerate(reference, 1):
        current = [i]
        for j, b in enumerate(hypothesis, 1):
            current.append(min(previous[j] + 1, current[-1] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]
