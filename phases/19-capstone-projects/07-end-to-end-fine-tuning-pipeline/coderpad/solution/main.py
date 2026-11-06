"""Original interview practice for 19-capstone-projects/07-end-to-end-fine-tuning-pipeline.

Local source: phases/19-capstone-projects/07-end-to-end-fine-tuning-pipeline/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def learning_rate(step, total, warmup, peak):
    if any((type(x) is not int for x in (step, total, warmup))) or total <= 0 or (not 0 <= warmup < total) or (step < 0) or (peak < 0):
        raise ValueError('schedule')
    if step < warmup:
        return peak * step / warmup
    return peak * (1 + math.cos(math.pi * min(1, (step - warmup) / (total - warmup)))) / 2

def lora_delta(a, b, alpha):
    if not a or not b or (not a[0]) or (not b[0]) or any((len(r) != len(a[0]) for r in a)) or any((len(r) != len(b[0]) for r in b)) or (len(a[0]) != len(b)):
        raise ValueError('shape')
    return [[alpha / len(b) * sum((row[k] * b[k][j] for k in range(len(b)))) for j in range(len(b[0]))] for row in a]
