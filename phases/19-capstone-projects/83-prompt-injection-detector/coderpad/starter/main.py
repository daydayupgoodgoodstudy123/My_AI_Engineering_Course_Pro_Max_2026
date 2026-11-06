"""Original interview practice for 19-capstone-projects/83-prompt-injection-detector.

Local source: phases/19-capstone-projects/83-prompt-injection-detector/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import re

def tokenize(text):
    """Casefold Unicode text, then return all contiguous ASCII [a-z0-9]+ tokens in order. Punctuation separates tokens. No stemming, stop-word removal or Unicode word matching."""
    raise NotImplementedError('TODO 1: tokenize; see PROMPT.md')

def unsupported_claims(claims, evidence_ids):
    """Claims have unique id(str) and references(list of evidence ids). Return sorted claim ids lacking references or containing any unknown reference. Duplicate claim ids raises ValueError. Having a reference verifies linkage only, not factual truth."""
    raise NotImplementedError('TODO 2: unsupported_claims; see PROMPT.md')
