"""Original interview practice for 19-capstone-projects/86-constitutional-rules-engine.

Local source: phases/19-capstone-projects/86-constitutional-rules-engine/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def validate_config(config, required, optional):
    missing = sorted(set(required) - set(config))
    unknown = sorted(set(config) - set(required) - set(optional))
    return {'missing': missing, 'unknown': unknown, 'valid': not missing and (not unknown)}

def moderation(signals, block_at):
    if type(block_at) is not int or not 0 <= block_at <= 3 or any((type(s['severity']) is not int or not 0 <= s['severity'] <= 3 for s in signals)):
        raise ValueError('severity')
    categories = {}
    for s in signals:
        categories[s['category']] = max(categories.get(s['category'], 0), s['severity'])
    return {'categories': dict(sorted(categories.items())), 'blocked': any((v >= block_at for v in categories.values()))}
