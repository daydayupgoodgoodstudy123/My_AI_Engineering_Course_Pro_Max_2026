"""Original interview practice for 10-llms-from-scratch/14-open-models-architecture-walkthroughs.

Local source: phases/10-llms-from-scratch/14-open-models-architecture-walkthroughs/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def parameter_memory(shapes, bytes_per_parameter):
    """Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError."""
    raise NotImplementedError('TODO 1: parameter_memory; see PROMPT.md')

def kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element):
    """All arguments are exact ints. layers,kv_heads,head_dimension,batch,bytes_per_element must be >0; tokens>=0. Return 2*layers*tokens*kv_heads*head_dimension*batch*bytes_per_element. Invalid input raises ValueError. No allocator overhead is included."""
    raise NotImplementedError('TODO 2: kv_bytes; see PROMPT.md')
