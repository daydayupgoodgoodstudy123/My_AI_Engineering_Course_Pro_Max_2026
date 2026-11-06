"""Original interview practice for 19-capstone-projects/14-speculative-decoding-server.

Local source: phases/19-capstone-projects/14-speculative-decoding-server/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def accept_prefix(draft, verified):
    i = 0
    while i < min(len(draft), len(verified)) and draft[i] == verified[i]:
        i += 1
    return {'accepted': draft[:i], 'next': verified[i] if i < len(verified) else None}

def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    values = [layers, tokens, kv_heads, head_dimension, batch, bytes_per_element]
    if any((type(v) is not int for v in values)) or tokens < 0 or any((v <= 0 for v in [layers, kv_heads, head_dimension, batch, bytes_per_element])):
        raise ValueError('dimensions')
    return 2 * layers * tokens * kv_heads * head_dimension * batch * bytes_per_element
