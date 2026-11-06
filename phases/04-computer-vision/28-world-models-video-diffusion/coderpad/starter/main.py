"""Original interview practice for 04-computer-vision/28-world-models-video-diffusion.

Local source: phases/04-computer-vision/28-world-models-video-diffusion/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def sample_frames(length, count):
    """Require exact nonnegative integers length/count and count<=length. Return count indices spanning 0..length-1 using floor(i*(length-1)/(count-1)). count=0 -> []; count=1 -> [0]. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 1: sample_frames; see PROMPT.md')

def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    """All arguments are exact ints. layers,kv_heads,head_dimension,batch,bytes_per_element must be >0; tokens>=0. Return 2*layers*tokens*kv_heads*head_dimension*batch*bytes_per_element. Invalid input raises ValueError. No allocator overhead is included."""
    raise NotImplementedError('TODO 2: kv_bytes; see PROMPT.md')
