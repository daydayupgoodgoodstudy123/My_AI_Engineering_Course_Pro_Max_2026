"""Original interview practice for 08-generative-ai/08-controlnet-lora-conditioning.

Local source: phases/08-generative-ai/08-controlnet-lora-conditioning/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def lora_delta(a, b, alpha):
    if not a or not b or (not a[0]) or (not b[0]) or any((len(r) != len(a[0]) for r in a)) or any((len(r) != len(b[0]) for r in b)) or (len(a[0]) != len(b)):
        raise ValueError('shape')
    return [[alpha / len(b) * sum((row[k] * b[k][j] for k in range(len(b)))) for j in range(len(b[0]))] for row in a]

def flow_step(state, velocity, delta):
    if len(state) != len(velocity) or not 0 <= delta <= 1:
        raise ValueError('contract')
    return [x + delta * v for x, v in zip(state, velocity)]
