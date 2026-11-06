"""Original interview practice for 17-infrastructure-and-production/06-sglang-radixattention.

Local source: phases/17-infrastructure-and-production/06-sglang-radixattention/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def lru_keys(accesses, capacity):
    if type(capacity) is not int or capacity < 0:
        raise ValueError('capacity')
    keys = []
    for key in accesses:
        if key in keys:
            keys.remove(key)
        keys.append(key)
        if len(keys) > capacity:
            keys.pop(0)
    return keys

def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    values = [layers, tokens, kv_heads, head_dimension, batch, bytes_per_element]
    if any((type(v) is not int for v in values)) or tokens < 0 or any((v <= 0 for v in [layers, kv_heads, head_dimension, batch, bytes_per_element])):
        raise ValueError('dimensions')
    return 2 * layers * tokens * kv_heads * head_dimension * batch * bytes_per_element
