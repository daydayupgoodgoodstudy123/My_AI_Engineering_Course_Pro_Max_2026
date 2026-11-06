"""Original interview practice for 05-nlp-foundations-to-advanced/29-dialogue-state-tracking.

Local source: phases/05-nlp-foundations-to-advanced/29-dialogue-state-tracking/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def update_slots(state, changes):
    """state and changes are dicts with only cuisine, area, people. Unknown keys in either raise ValueError. Changes with None delete a slot; other values replace it. Return a new merged dict without mutating either input. Value typing is upstream."""
    raise NotImplementedError('TODO 1: update_slots; see PROMPT.md')

def transition(state, target):
    """Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves."""
    raise NotImplementedError('TODO 2: transition; see PROMPT.md')
