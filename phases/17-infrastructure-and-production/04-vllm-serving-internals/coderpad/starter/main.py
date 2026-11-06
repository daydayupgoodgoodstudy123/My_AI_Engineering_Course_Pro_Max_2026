"""Original interview practice for 17-infrastructure-and-production/04-vllm-serving-internals.

Local source: phases/17-infrastructure-and-production/04-vllm-serving-internals/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    """All arguments are exact ints. layers,kv_heads,head_dimension,batch,bytes_per_element must be >0; tokens>=0. Return 2*layers*tokens*kv_heads*head_dimension*batch*bytes_per_element. Invalid input raises ValueError. No allocator overhead is included."""
    raise NotImplementedError('TODO 1: kv_bytes; see PROMPT.md')

def make_batches(items, maximum):
    """items are {'id','tokens':exact positive int}; maximum exact positive int. Preserve input order, greedily pack consecutive items while sum tokens<=maximum. Oversized item raises ValueError rather than silently dropping it. Return list of lists of ids; empty input yields []."""
    raise NotImplementedError('TODO 2: make_batches; see PROMPT.md')
