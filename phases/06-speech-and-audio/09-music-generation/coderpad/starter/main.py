"""Original interview practice for 06-speech-and-audio/09-music-generation.

Local source: phases/06-speech-and-audio/09-music-generation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
from collections import Counter

def ngram_counts(tokens, n):
    """n is exact positive int. Return a dict whose keys are JSON strings encoding each token window (json.dumps defaults) and whose values are counts. n>len(tokens) or empty tokens returns {}. Invalid n raises ValueError."""
    raise NotImplementedError('TODO 1: ngram_counts; see PROMPT.md')

def inverse_cdf(probabilities, uniforms):
    """Probabilities must be nonempty, nonnegative, sum to 1 within 1e-9. Each uniform is in [0,1). Return the first index whose cumulative probability is strictly greater than u. Invalid input raises ValueError; empty uniforms returns []. No RNG is called."""
    raise NotImplementedError('TODO 2: inverse_cdf; see PROMPT.md')
