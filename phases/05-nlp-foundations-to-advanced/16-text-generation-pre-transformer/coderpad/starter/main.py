"""Original interview practice for 05-nlp-foundations-to-advanced/16-text-generation-pre-transformer.

Local source: phases/05-nlp-foundations-to-advanced/16-text-generation-pre-transformer/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math
import json
from collections import Counter

def perplexity(probabilities):
    """Return exp(-mean(log(p))) for nonempty true-token probabilities, each 0<p<=1. Invalid inputs raise ValueError. Probabilities are not required to sum to 1 because each refers to a different timestep."""
    raise NotImplementedError('TODO 1: perplexity; see PROMPT.md')

def ngram_counts(tokens, n):
    """n is exact positive int. Return a dict whose keys are JSON strings encoding each token window (json.dumps defaults) and whose values are counts. n>len(tokens) or empty tokens returns {}. Invalid n raises ValueError."""
    raise NotImplementedError('TODO 2: ngram_counts; see PROMPT.md')
