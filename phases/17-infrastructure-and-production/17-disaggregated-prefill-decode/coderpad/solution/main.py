"""Original interview practice for 17-infrastructure-and-production/17-disaggregated-prefill-decode.

Local source: phases/17-infrastructure-and-production/17-disaggregated-prefill-decode/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def schedule_jobs(jobs, capacity):
    if type(capacity) is not int or capacity < 0 or len({j['id'] for j in jobs}) != len(jobs):
        raise ValueError('queue')
    return [j['id'] for j in sorted((j for j in jobs if j['status'] == 'queued'), key=lambda j: (-j['priority'], j['created'], j['id']))[:capacity]]

def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    values = [layers, tokens, kv_heads, head_dimension, batch, bytes_per_element]
    if any((type(v) is not int for v in values)) or tokens < 0 or any((v <= 0 for v in [layers, kv_heads, head_dimension, batch, bytes_per_element])):
        raise ValueError('dimensions')
    return 2 * layers * tokens * kv_heads * head_dimension * batch * bytes_per_element
