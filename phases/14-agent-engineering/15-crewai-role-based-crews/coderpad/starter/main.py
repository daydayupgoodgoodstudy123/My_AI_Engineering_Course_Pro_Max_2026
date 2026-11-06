"""Original interview practice for 14-agent-engineering/15-crewai-role-based-crews.

Local source: phases/14-agent-engineering/15-crewai-role-based-crews/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def route_task(routes, query_tokens, role):
    """Each route has name(str), roles(list), keywords(list). Among role-eligible routes, score set intersection with query_tokens. Return unique highest positive-scoring name. No positive match or a tie returns None. Duplicate route names raise ValueError; input order must not resolve a tie."""
    raise NotImplementedError('TODO 1: route_task; see PROMPT.md')

def validate_handoff(bundle):
    """Required nonempty string fields: objective, state, next_action. checks must be a nonempty list of nonempty strings. Return sorted missing/invalid field names (among those four). Extra fields allowed; whitespace-only strings are invalid. Do not execute next_action."""
    raise NotImplementedError('TODO 2: validate_handoff; see PROMPT.md')
