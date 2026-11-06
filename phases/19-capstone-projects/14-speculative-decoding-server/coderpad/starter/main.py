"""Original interview practice for 19-capstone-projects/14-speculative-decoding-server.

Local source: phases/19-capstone-projects/14-speculative-decoding-server/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def accept_prefix(draft, verified):
    """Return {'accepted':longest matching prefix of draft and verified, 'next':first verified token after that prefix or None}. draft may be shorter; verified may be empty. Exact token equality; no probabilities or sampling are modeled."""
    raise NotImplementedError('TODO 1: accept_prefix; see PROMPT.md')

def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    """All arguments are exact ints. layers,kv_heads,head_dimension,batch,bytes_per_element must be >0; tokens>=0. Return 2*layers*tokens*kv_heads*head_dimension*batch*bytes_per_element. Invalid input raises ValueError. No allocator overhead is included."""
    raise NotImplementedError('TODO 2: kv_bytes; see PROMPT.md')
