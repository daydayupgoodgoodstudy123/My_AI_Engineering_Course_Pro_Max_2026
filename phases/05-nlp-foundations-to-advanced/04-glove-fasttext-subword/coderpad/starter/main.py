"""Original interview practice for 05-nlp-foundations-to-advanced/04-glove-fasttext-subword.

Local source: phases/05-nlp-foundations-to-advanced/04-glove-fasttext-subword/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import re

def merge_pair(tokens, pair):
    """pair must contain exactly two strings. Scan tokens left to right, replacing each non-overlapping adjacent match with concatenation. Preserve unmatched tokens. Invalid pair raises ValueError; input lists do not mutate."""
    raise NotImplementedError('TODO 1: merge_pair; see PROMPT.md')

def tokenize(text):
    """Casefold Unicode text, then return all contiguous ASCII [a-z0-9]+ tokens in order. Punctuation separates tokens. No stemming, stop-word removal or Unicode word matching."""
    raise NotImplementedError('TODO 2: tokenize; see PROMPT.md')
