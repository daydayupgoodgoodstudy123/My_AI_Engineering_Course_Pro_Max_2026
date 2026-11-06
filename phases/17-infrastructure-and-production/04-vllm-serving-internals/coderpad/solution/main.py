"""Original interview practice for 17-infrastructure-and-production/04-vllm-serving-internals.

Local source: phases/17-infrastructure-and-production/04-vllm-serving-internals/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    values = [layers, tokens, kv_heads, head_dimension, batch, bytes_per_element]
    if any((type(v) is not int for v in values)) or tokens < 0 or any((v <= 0 for v in [layers, kv_heads, head_dimension, batch, bytes_per_element])):
        raise ValueError('dimensions')
    return 2 * layers * tokens * kv_heads * head_dimension * batch * bytes_per_element

def make_batches(items, maximum):
    if type(maximum) is not int or maximum <= 0 or any((type(x['tokens']) is not int or not 0 < x['tokens'] <= maximum for x in items)):
        raise ValueError('batch')
    result = []
    current = []
    size = 0
    for x in items:
        if size + x['tokens'] > maximum:
            result.append(current)
            current = []
            size = 0
        current.append(x['id'])
        size += x['tokens']
    if current:
        result.append(current)
    return result
