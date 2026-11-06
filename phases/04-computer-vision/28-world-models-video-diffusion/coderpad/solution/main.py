"""Original interview practice for 04-computer-vision/28-world-models-video-diffusion.

Local source: phases/04-computer-vision/28-world-models-video-diffusion/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def sample_frames(length, count):
    if type(length) is not int or type(count) is not int or (not 0 <= count <= length):
        raise ValueError('frames')
    if count == 0:
        return []
    if count == 1:
        return [0]
    return [i * (length - 1) // (count - 1) for i in range(count)]

def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    values = [layers, tokens, kv_heads, head_dimension, batch, bytes_per_element]
    if any((type(v) is not int for v in values)) or tokens < 0 or any((v <= 0 for v in [layers, kv_heads, head_dimension, batch, bytes_per_element])):
        raise ValueError('dimensions')
    return 2 * layers * tokens * kv_heads * head_dimension * batch * bytes_per_element
