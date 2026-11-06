"""Original interview practice for 10-llms-from-scratch/09-constitutional-ai-self-improvement.

Local source: phases/10-llms-from-scratch/09-constitutional-ai-self-improvement/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def moderation(signals, block_at):
    if type(block_at) is not int or not 0 <= block_at <= 3 or any((type(s['severity']) is not int or not 0 <= s['severity'] <= 3 for s in signals)):
        raise ValueError('severity')
    categories = {}
    for s in signals:
        categories[s['category']] = max(categories.get(s['category'], 0), s['severity'])
    return {'categories': dict(sorted(categories.items())), 'blocked': any((v >= block_at for v in categories.values()))}

def evidence_gate(evidence, required):
    failed = sorted((k for k in set(required) if evidence.get(k) is not True))
    return {'ready': not failed, 'failed': failed}
