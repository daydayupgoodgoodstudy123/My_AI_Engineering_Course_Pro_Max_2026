"""Original interview practice for 07-transformers-deep-dive/16-speculative-decoding.

Local source: phases/07-transformers-deep-dive/16-speculative-decoding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def accept_prefix(draft, verified):
    """Return {'accepted':longest matching prefix of draft and verified, 'next':first verified token after that prefix or None}. draft may be shorter; verified may be empty. Exact token equality; no probabilities or sampling are modeled."""
    raise NotImplementedError('TODO 1: accept_prefix; see PROMPT.md')

def perplexity(probabilities):
    """Return exp(-mean(log(p))) for nonempty true-token probabilities, each 0<p<=1. Invalid inputs raise ValueError. Probabilities are not required to sum to 1 because each refers to a different timestep."""
    raise NotImplementedError('TODO 2: perplexity; see PROMPT.md')
