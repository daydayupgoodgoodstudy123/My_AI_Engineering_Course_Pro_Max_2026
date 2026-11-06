"""Original interview practice for 16-multi-agent-and-swarms/08-role-specialization.

Local source: phases/16-multi-agent-and-swarms/08-role-specialization/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def route_task(routes, query_tokens, role):
    """Each route has name(str), roles(list), keywords(list). Among role-eligible routes, score set intersection with query_tokens. Return unique highest positive-scoring name. No positive match or a tie returns None. Duplicate route names raise ValueError; input order must not resolve a tie."""
    raise NotImplementedError('TODO 1: route_task; see PROMPT.md')

def permission_decision(capability, granted, side_effect, approved):
    """If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes."""
    raise NotImplementedError('TODO 2: permission_decision; see PROMPT.md')
