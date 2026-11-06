"""Original interview practice for 18-ethics-safety-alignment/30-dual-use-risk-cyber-bio-chem-nuclear.

Local source: phases/18-ethics-safety-alignment/30-dual-use-risk-cyber-bio-chem-nuclear/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def prioritize_risks(risks):
    if len({r['id'] for r in risks}) != len(risks) or any((type(r[k]) is not int or not 1 <= r[k] <= 5 for r in risks for k in ('severity', 'likelihood'))):
        raise ValueError('risk')
    return [r['id'] for r in sorted(risks, key=lambda r: (-r['severity'] * r['likelihood'], -r['severity'], r['id']))]

def permission_decision(capability, granted, side_effect, approved):
    if type(side_effect) is not bool or type(approved) is not bool:
        raise ValueError('flags')
    if capability not in granted:
        return 'deny'
    return 'ask' if side_effect and (not approved) else 'allow'
