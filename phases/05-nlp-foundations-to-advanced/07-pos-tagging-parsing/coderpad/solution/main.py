"""Original interview practice for 05-nlp-foundations-to-advanced/07-pos-tagging-parsing.

Local source: phases/05-nlp-foundations-to-advanced/07-pos-tagging-parsing/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def markov_step(distribution, transition):
    n = len(distribution)
    if not n or len(transition) != n or any((len(r) != n for r in transition)) or any((p < 0 for r in [distribution] + transition for p in r)) or any((abs(sum(r) - 1) > 1e-09 for r in [distribution] + transition)):
        raise ValueError('stochastic matrix')
    return [sum((distribution[i] * transition[i][j] for i in range(n))) for j in range(n)]

def top_k(scores, k):
    if type(k) is not int or not 0 <= k <= len(scores):
        raise ValueError('k')
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]
