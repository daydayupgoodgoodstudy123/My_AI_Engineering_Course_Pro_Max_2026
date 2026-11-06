"""Original interview practice for 06-speech-and-audio/09-music-generation.

Local source: phases/06-speech-and-audio/09-music-generation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
from collections import Counter

def ngram_counts(tokens, n):
    if type(n) is not int or n <= 0:
        raise ValueError('n')
    return dict(Counter((json.dumps(tokens[i:i + n]) for i in range(len(tokens) - n + 1))))

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
