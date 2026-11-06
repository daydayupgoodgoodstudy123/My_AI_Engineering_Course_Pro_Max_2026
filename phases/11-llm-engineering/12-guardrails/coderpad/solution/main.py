"""Original interview practice for 11-llm-engineering/12-guardrails.

Local source: phases/11-llm-engineering/12-guardrails/docs/en.md (sha256 in SCOPE.json).
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

def permission_decision(capability, granted, side_effect, approved):
    if type(side_effect) is not bool or type(approved) is not bool:
        raise ValueError('flags')
    if capability not in granted:
        return 'deny'
    return 'ask' if side_effect and (not approved) else 'allow'
