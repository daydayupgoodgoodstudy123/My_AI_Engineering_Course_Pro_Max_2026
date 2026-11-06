"""Original interview practice for 19-capstone-projects/85-content-classifier-integration.

Local source: phases/19-capstone-projects/85-content-classifier-integration/docs/en.md (sha256 in SCOPE.json).
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

def prioritize_risks(risks):
    if len({r['id'] for r in risks}) != len(risks) or any((type(r[k]) is not int or not 1 <= r[k] <= 5 for r in risks for k in ('severity', 'likelihood'))):
        raise ValueError('risk')
    return [r['id'] for r in sorted(risks, key=lambda r: (-r['severity'] * r['likelihood'], -r['severity'], r['id']))]
