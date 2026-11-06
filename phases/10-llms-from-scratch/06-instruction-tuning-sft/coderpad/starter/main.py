"""Original interview practice for 10-llms-from-scratch/06-instruction-tuning-sft.

Local source: phases/10-llms-from-scratch/06-instruction-tuning-sft/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def masked_probabilities(logits, allowed):
    """allowed is a list of unique valid indices; return softmax over allowed logits with 0 at every disallowed index. Preserve original output length. Empty allowed, duplicate/out-of-range/non-int index, or empty logits raises ValueError. Use stable exponentiation."""
    raise NotImplementedError('TODO 1: masked_probabilities; see PROMPT.md')

def cross_entropy(probabilities, target):
    """Require nonempty nonnegative probabilities summing to 1 within 1e-9 and exact integer target index in range. Return -log(probabilities[target]); use clamp minimum 1e-12. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 2: cross_entropy; see PROMPT.md')
