"""Original interview practice for 11-llm-engineering/08-fine-tuning-lora.

Local source: phases/11-llm-engineering/08-fine-tuning-lora/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def lora_delta(a, b, alpha):
    if not a or not b or (not a[0]) or (not b[0]) or any((len(r) != len(a[0]) for r in a)) or any((len(r) != len(b[0]) for r in b)) or (len(a[0]) != len(b)):
        raise ValueError('shape')
    return [[alpha / len(b) * sum((row[k] * b[k][j] for k in range(len(b)))) for j in range(len(b[0]))] for row in a]

def parameter_memory(shapes, bytes_per_parameter):
    if type(bytes_per_parameter) is not int or bytes_per_parameter <= 0 or any((type(d) is not int or d <= 0 for shape in shapes for d in shape)):
        raise ValueError('shape')
    return sum((math.prod(shape) for shape in shapes)) * bytes_per_parameter
