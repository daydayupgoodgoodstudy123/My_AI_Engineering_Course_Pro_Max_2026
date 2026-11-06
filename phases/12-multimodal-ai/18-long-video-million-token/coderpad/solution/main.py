"""Original interview practice for 12-multimodal-ai/18-long-video-million-token.

Local source: phases/12-multimodal-ai/18-long-video-million-token/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def select_context(items, budget):
    if type(budget) is not int or budget < 0 or any((type(x['tokens']) is not int or x['tokens'] < 0 for x in items)):
        raise ValueError('budget')
    result = []
    for item in sorted(items, key=lambda x: (-x['score'], x['id'])):
        if item['tokens'] <= budget:
            result.append(item['id'])
            budget -= item['tokens']
    return result

def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    values = [layers, tokens, kv_heads, head_dimension, batch, bytes_per_element]
    if any((type(v) is not int for v in values)) or tokens < 0 or any((v <= 0 for v in [layers, kv_heads, head_dimension, batch, bytes_per_element])):
        raise ValueError('dimensions')
    return 2 * layers * tokens * kv_heads * head_dimension * batch * bytes_per_element
