"""Original interview practice for 08-generative-ai/02-autoencoders-vae.

Local source: phases/08-generative-ai/02-autoencoders-vae/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def mse(predicted, expected):
    if not predicted or len(predicted) != len(expected):
        raise ValueError('shape')
    return sum(((a - b) ** 2 for a, b in zip(predicted, expected))) / len(predicted)

def inverse_cdf(probabilities, uniforms):
    if not probabilities or any((p < 0 for p in probabilities)) or abs(sum(probabilities) - 1) > 1e-09 or any((not 0 <= u < 1 for u in uniforms)):
        raise ValueError('distribution')
    result = []
    for u in uniforms:
        cumulative = 0
        for i, p in enumerate(probabilities):
            cumulative += p
            if u < cumulative:
                result.append(i)
                break
        else:
            result.append(len(probabilities) - 1)
    return result
