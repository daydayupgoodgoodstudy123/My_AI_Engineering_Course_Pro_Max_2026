"""Original interview practice for 01-math-foundations/16-sampling-methods.

Local source: phases/01-math-foundations/16-sampling-methods/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


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

def markov_step(distribution, transition):
    n = len(distribution)
    if not n or len(transition) != n or any((len(r) != n for r in transition)) or any((p < 0 for r in [distribution] + transition for p in r)) or any((abs(sum(r) - 1) > 1e-09 for r in [distribution] + transition)):
        raise ValueError('stochastic matrix')
    return [sum((distribution[i] * transition[i][j] for i in range(n))) for j in range(n)]
