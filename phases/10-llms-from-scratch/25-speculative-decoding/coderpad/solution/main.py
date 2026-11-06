"""Original interview practice for 10-llms-from-scratch/25-speculative-decoding.

Local source: phases/10-llms-from-scratch/25-speculative-decoding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def accept_prefix(draft, verified):
    i = 0
    while i < min(len(draft), len(verified)) and draft[i] == verified[i]:
        i += 1
    return {'accepted': draft[:i], 'next': verified[i] if i < len(verified) else None}

def causal_mask(length, window=None):
    if type(length) is not int or length < 0 or (window is not None and (type(window) is not int or window <= 0)):
        raise ValueError('shape')
    return [[j <= i and (window is None or i - j < window) for j in range(length)] for i in range(length)]
