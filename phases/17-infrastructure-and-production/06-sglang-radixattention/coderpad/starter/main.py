"""Original interview practice for 17-infrastructure-and-production/06-sglang-radixattention.

Local source: phases/17-infrastructure-and-production/06-sglang-radixattention/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def lru_keys(accesses, capacity):
    """Replay string-key accesses in a cache of exact nonnegative integer capacity. Every access inserts/touches the key. Evict least recently used when full. Return final keys from least to most recent. capacity 0 returns []; invalid capacity raises ValueError."""
    raise NotImplementedError('TODO 1: lru_keys; see PROMPT.md')

def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    """All arguments are exact ints. layers,kv_heads,head_dimension,batch,bytes_per_element must be >0; tokens>=0. Return 2*layers*tokens*kv_heads*head_dimension*batch*bytes_per_element. Invalid input raises ValueError. No allocator overhead is included."""
    raise NotImplementedError('TODO 2: kv_bytes; see PROMPT.md')
