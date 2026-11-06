"""Original interview practice for 15-autonomous-systems/09-coding-agent-landscape.

Local source: phases/15-autonomous-systems/09-coding-agent-landscape/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def route_task(routes, query_tokens, role):
    """Each route has name(str), roles(list), keywords(list). Among role-eligible routes, score set intersection with query_tokens. Return unique highest positive-scoring name. No positive match or a tie returns None. Duplicate route names raise ValueError; input order must not resolve a tie."""
    raise NotImplementedError('TODO 1: route_task; see PROMPT.md')

def validate_config(config, required, optional):
    """required and optional are field-name lists. Return {'missing':sorted required absent keys,'unknown':sorted config keys outside required+optional,'valid':no findings}. Values are deliberately not type-checked here. Empty config can be valid."""
    raise NotImplementedError('TODO 2: validate_config; see PROMPT.md')
