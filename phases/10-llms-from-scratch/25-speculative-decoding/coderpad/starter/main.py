"""Original interview practice for 10-llms-from-scratch/25-speculative-decoding.

Local source: phases/10-llms-from-scratch/25-speculative-decoding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def accept_prefix(draft, verified):
    """Return {'accepted':longest matching prefix of draft and verified, 'next':first verified token after that prefix or None}. draft may be shorter; verified may be empty. Exact token equality; no probabilities or sampling are modeled."""
    raise NotImplementedError('TODO 1: accept_prefix; see PROMPT.md')

def causal_mask(length, window=None):
    """Return length x length booleans where row i may attend column j iff j<=i and, if window provided, i-j<window. length exact int >=0; window None or exact positive int. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 2: causal_mask; see PROMPT.md')
