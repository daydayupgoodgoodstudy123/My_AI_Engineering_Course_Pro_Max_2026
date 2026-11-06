"""Original interview practice for 15-autonomous-systems/20-openai-preparedness-deepmind-fsf.

Local source: phases/15-autonomous-systems/20-openai-preparedness-deepmind-fsf/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def evidence_gate(evidence, required):
    failed = sorted((k for k in set(required) if evidence.get(k) is not True))
    return {'ready': not failed, 'failed': failed}

def prioritize_risks(risks):
    if len({r['id'] for r in risks}) != len(risks) or any((type(r[k]) is not int or not 1 <= r[k] <= 5 for r in risks for k in ('severity', 'likelihood'))):
        raise ValueError('risk')
    return [r['id'] for r in sorted(risks, key=lambda r: (-r['severity'] * r['likelihood'], -r['severity'], r['id']))]
