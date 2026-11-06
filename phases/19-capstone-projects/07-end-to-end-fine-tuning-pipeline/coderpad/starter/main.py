"""Original interview practice for 19-capstone-projects/07-end-to-end-fine-tuning-pipeline.

Local source: phases/19-capstone-projects/07-end-to-end-fine-tuning-pipeline/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def learning_rate(step, total, warmup, peak):
    """Require exact integer total>0, 0<=warmup<total, step>=0, and peak>=0. If step<warmup return peak*step/warmup; otherwise peak*(1+cos(pi*min(1,(step-warmup)/(total-warmup))))/2. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: learning_rate; see PROMPT.md')

def lora_delta(a, b, alpha):
    """A is nonempty output-by-rank, B is rank-by-input, both rectangular with nonempty rows. Return (alpha/rank)*A@B; alpha is finite numeric. Invalid shapes raise ValueError. No base weights are modified."""
    raise NotImplementedError('TODO 2: lora_delta; see PROMPT.md')
