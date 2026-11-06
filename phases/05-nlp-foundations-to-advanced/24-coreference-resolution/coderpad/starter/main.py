"""Original interview practice for 05-nlp-foundations-to-advanced/24-coreference-resolution.

Local source: phases/05-nlp-foundations-to-advanced/24-coreference-resolution/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def bio_spans(labels):
    """Labels are O, B-TYPE or I-TYPE with nonempty TYPE. Return {'type','start','end'} spans with half-open indices. I-TYPE without matching active type is treated as B-TYPE. Invalid label syntax raises ValueError. Consecutive B labels always start new entities."""
    raise NotImplementedError('TODO 1: bio_spans; see PROMPT.md')

def update_slots(state, changes):
    """state and changes are dicts with only cuisine, area, people. Unknown keys in either raise ValueError. Changes with None delete a slot; other values replace it. Return a new merged dict without mutating either input. Value typing is upstream."""
    raise NotImplementedError('TODO 2: update_slots; see PROMPT.md')
