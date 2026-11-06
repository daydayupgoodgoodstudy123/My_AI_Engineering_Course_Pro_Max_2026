"""Original interview practice for 11-llm-engineering/02-few-shot-cot.

Local source: phases/11-llm-engineering/02-few-shot-cot/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def select_context(items, budget):
    if type(budget) is not int or budget < 0 or any((type(x['tokens']) is not int or x['tokens'] < 0 for x in items)):
        raise ValueError('budget')
    result = []
    for item in sorted(items, key=lambda x: (-x['score'], x['id'])):
        if item['tokens'] <= budget:
            result.append(item['id'])
            budget -= item['tokens']
    return result

def token_f1(reference, answer):
    if not reference or not answer:
        return 1 if not reference and (not answer) else 0
    overlap = sum((Counter(reference) & Counter(answer)).values())
    p = overlap / len(answer)
    r = overlap / len(reference)
    return 2 * p * r / (p + r) if p + r else 0
