"""Original interview practice for 01-math-foundations/06-probability-and-distributions.

Local source: phases/01-math-foundations/06-probability-and-distributions/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

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

def entropy(probabilities):
    if not probabilities or any((p < 0 or p > 1 for p in probabilities)) or abs(sum(probabilities) - 1) > 1e-09:
        raise ValueError('distribution')
    return -sum((p * math.log2(p) for p in probabilities if p))
