"""Original interview practice for 16-multi-agent-and-swarms/01-why-multi-agent.

Local source: phases/16-multi-agent-and-swarms/01-why-multi-agent/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def amdahl(serial_fraction, speedup):
    """Return 1/(serial_fraction+(1-serial_fraction)/speedup). Require serial_fraction in [0,1] and speedup>=1; otherwise ValueError. This models latency, not queueing throughput."""
    raise NotImplementedError('TODO 1: amdahl; see PROMPT.md')

def token_cost(usage, prices):
    """usage rows contain provider,input_tokens,output_tokens exact nonnegative ints. prices maps provider to [input_price,output_price] per token, nonnegative. Return {'total':sum,'by_provider':sums}. Unknown provider raises KeyError; negative/invalid counts or prices raises ValueError. Empty usage yields zero totals."""
    raise NotImplementedError('TODO 2: token_cost; see PROMPT.md')
