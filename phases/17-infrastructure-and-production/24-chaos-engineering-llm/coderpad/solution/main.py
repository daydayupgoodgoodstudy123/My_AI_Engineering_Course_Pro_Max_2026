"""Original interview practice for 17-infrastructure-and-production/24-chaos-engineering-llm.

Local source: phases/17-infrastructure-and-production/24-chaos-engineering-llm/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def retry_delays(attempts, base, cap):
    if type(attempts) is not int or not 0 <= attempts <= 30 or base < 0 or (cap < 0):
        raise ValueError('retry')
    return [min(cap, base * 2 ** i) for i in range(attempts)]

def evidence_gate(evidence, required):
    failed = sorted((k for k in set(required) if evidence.get(k) is not True))
    return {'ready': not failed, 'failed': failed}
