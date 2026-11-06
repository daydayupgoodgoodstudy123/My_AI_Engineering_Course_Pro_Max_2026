"""Original interview practice for 16-multi-agent-and-swarms/18-theory-of-mind-coordination.

Local source: phases/16-multi-agent-and-swarms/18-theory-of-mind-coordination/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bayes(prior, likelihood_positive, likelihood_negative):
    """For three probabilities in [0,1], return P(H|E)=prior*likelihood_positive/(prior*likelihood_positive+(1-prior)*likelihood_negative). Out-of-range values or zero evidence probability raise ValueError."""
    raise NotImplementedError('TODO 1: bayes; see PROMPT.md')

def route_task(routes, query_tokens, role):
    """Each route has name(str), roles(list), keywords(list). Among role-eligible routes, score set intersection with query_tokens. Return unique highest positive-scoring name. No positive match or a tie returns None. Duplicate route names raise ValueError; input order must not resolve a tie."""
    raise NotImplementedError('TODO 2: route_task; see PROMPT.md')
