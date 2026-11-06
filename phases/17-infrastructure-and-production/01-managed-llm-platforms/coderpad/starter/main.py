"""Original interview practice for 17-infrastructure-and-production/01-managed-llm-platforms.

Local source: phases/17-infrastructure-and-production/01-managed-llm-platforms/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def route_task(routes, query_tokens, role):
    """Each route has name(str), roles(list), keywords(list). Among role-eligible routes, score set intersection with query_tokens. Return unique highest positive-scoring name. No positive match or a tie returns None. Duplicate route names raise ValueError; input order must not resolve a tie."""
    raise NotImplementedError('TODO 1: route_task; see PROMPT.md')

def token_cost(usage, prices):
    """usage rows contain provider,input_tokens,output_tokens exact nonnegative ints. prices maps provider to [input_price,output_price] per token, nonnegative. Return {'total':sum,'by_provider':sums}. Unknown provider raises KeyError; negative/invalid counts or prices raises ValueError. Empty usage yields zero totals."""
    raise NotImplementedError('TODO 2: token_cost; see PROMPT.md')
