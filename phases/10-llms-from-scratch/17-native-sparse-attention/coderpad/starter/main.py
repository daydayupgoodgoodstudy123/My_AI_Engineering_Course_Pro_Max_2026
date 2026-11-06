"""Original interview practice for 10-llms-from-scratch/17-native-sparse-attention.

Local source: phases/10-llms-from-scratch/17-native-sparse-attention/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def causal_mask(length, window=None):
    """Return length x length booleans where row i may attend column j iff j<=i and, if window provided, i-j<window. length exact int >=0; window None or exact positive int. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: causal_mask; see PROMPT.md')

def top_k(scores, k):
    """Return the indices of k largest scores, descending score with lower original index ties. k exact int in [0,len(scores)], else ValueError; k=0 returns []."""
    raise NotImplementedError('TODO 2: top_k; see PROMPT.md')
