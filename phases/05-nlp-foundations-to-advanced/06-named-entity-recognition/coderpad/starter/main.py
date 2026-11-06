"""Original interview practice for 05-nlp-foundations-to-advanced/06-named-entity-recognition.

Local source: phases/05-nlp-foundations-to-advanced/06-named-entity-recognition/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import re

def bio_spans(labels):
    """Labels are O, B-TYPE or I-TYPE with nonempty TYPE. Return {'type','start','end'} spans with half-open indices. I-TYPE without matching active type is treated as B-TYPE. Invalid label syntax raises ValueError. Consecutive B labels always start new entities."""
    raise NotImplementedError('TODO 1: bio_spans; see PROMPT.md')

def tokenize(text):
    """Casefold Unicode text, then return all contiguous ASCII [a-z0-9]+ tokens in order. Punctuation separates tokens. No stemming, stop-word removal or Unicode word matching."""
    raise NotImplementedError('TODO 2: tokenize; see PROMPT.md')
