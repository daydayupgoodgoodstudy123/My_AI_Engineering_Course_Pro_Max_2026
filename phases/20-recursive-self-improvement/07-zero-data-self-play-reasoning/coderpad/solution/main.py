"""Original interview practice for 20-recursive-self-improvement/07-zero-data-self-play-reasoning.

Local source: phases/20-recursive-self-improvement/07-zero-data-self-play-reasoning/docs/en.md (sha256 in SCOPE.json).
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

def evidence_gate(evidence, required):
    failed = sorted((k for k in set(required) if evidence.get(k) is not True))
    return {'ready': not failed, 'failed': failed}
