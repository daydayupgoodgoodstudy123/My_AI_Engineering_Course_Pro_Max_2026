"""Original interview practice for 05-nlp-foundations-to-advanced/17-chatbots-rule-to-neural.

Local source: phases/05-nlp-foundations-to-advanced/17-chatbots-rule-to-neural/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def route_task(routes, query_tokens, role):
    """Each route has name(str), roles(list), keywords(list). Among role-eligible routes, score set intersection with query_tokens. Return unique highest positive-scoring name. No positive match or a tie returns None. Duplicate route names raise ValueError; input order must not resolve a tie."""
    raise NotImplementedError('TODO 1: route_task; see PROMPT.md')

def update_slots(state, changes):
    """state and changes are dicts with only cuisine, area, people. Unknown keys in either raise ValueError. Changes with None delete a slot; other values replace it. Return a new merged dict without mutating either input. Value typing is upstream."""
    raise NotImplementedError('TODO 2: update_slots; see PROMPT.md')
