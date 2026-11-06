"""Original interview practice for 17-infrastructure-and-production/09-production-quantization.

Local source: phases/17-infrastructure-and-production/09-production-quantization/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def quantize(values, bits):
    if type(bits) is not int or not 2 <= bits <= 8:
        raise ValueError('bits')
    bound = 2 ** (bits - 1) - 1
    maximum = max((abs(x) for x in values), default=0)
    scale = maximum / bound if maximum else 1
    return {'values': [max(-bound, min(bound, round(x / scale))) for x in values], 'scale': scale}

def mse(predicted, expected):
    if not predicted or len(predicted) != len(expected):
        raise ValueError('shape')
    return sum(((a - b) ** 2 for a, b in zip(predicted, expected))) / len(predicted)
