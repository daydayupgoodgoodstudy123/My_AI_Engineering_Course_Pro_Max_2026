"""Original interview practice for 19-capstone-projects/33-multihead-self-attention.

Local source: phases/19-capstone-projects/33-multihead-self-attention/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def attention(query, keys, values):
    """query is nonempty length d; keys is nonempty NxD and values is NxV with nonempty equal row widths. Compute softmax(query dot key / sqrt(d)) then the weighted sum of value rows. Invalid shapes raise ValueError; implement with Python lists."""
    raise NotImplementedError('TODO 1: attention; see PROMPT.md')

def matmul(a, b):
    """Multiply nonempty rectangular numeric matrices using row-by-column products. Reject empty matrices, ragged rows, empty rows or incompatible inner dimensions with ValueError."""
    raise NotImplementedError('TODO 2: matmul; see PROMPT.md')
