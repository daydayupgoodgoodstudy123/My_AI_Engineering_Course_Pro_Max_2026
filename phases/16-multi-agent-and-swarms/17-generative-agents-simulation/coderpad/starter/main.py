"""Original interview practice for 16-multi-agent-and-swarms/17-generative-agents-simulation.

Local source: phases/16-multi-agent-and-swarms/17-generative-agents-simulation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def markov_step(distribution, transition):
    """Distribution is a nonempty probability row vector; transition is an NxN row-stochastic matrix. Reject wrong shapes, negatives or row/distribution sums outside 1e-9 with ValueError. Return distribution @ transition."""
    raise NotImplementedError('TODO 1: markov_step; see PROMPT.md')

def route_task(routes, query_tokens, role):
    """Each route has name(str), roles(list), keywords(list). Among role-eligible routes, score set intersection with query_tokens. Return unique highest positive-scoring name. No positive match or a tie returns None. Duplicate route names raise ValueError; input order must not resolve a tie."""
    raise NotImplementedError('TODO 2: route_task; see PROMPT.md')
