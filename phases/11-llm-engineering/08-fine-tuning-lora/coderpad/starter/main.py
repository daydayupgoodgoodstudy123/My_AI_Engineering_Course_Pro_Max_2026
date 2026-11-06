"""Original interview practice for 11-llm-engineering/08-fine-tuning-lora.

Local source: phases/11-llm-engineering/08-fine-tuning-lora/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def lora_delta(a, b, alpha):
    """A is nonempty output-by-rank, B is rank-by-input, both rectangular with nonempty rows. Return (alpha/rank)*A@B; alpha is finite numeric. Invalid shapes raise ValueError. No base weights are modified."""
    raise NotImplementedError('TODO 1: lora_delta; see PROMPT.md')

def parameter_memory(shapes, bytes_per_parameter):
    """Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError."""
    raise NotImplementedError('TODO 2: parameter_memory; see PROMPT.md')
