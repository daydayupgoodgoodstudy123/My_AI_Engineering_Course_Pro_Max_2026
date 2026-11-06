"""Original interview practice for 18-ethics-safety-alignment/06-mesa-optimization-deceptive-alignment.

Local source: phases/18-ethics-safety-alignment/06-mesa-optimization-deceptive-alignment/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def evidence_gate(evidence, required):
    failed = sorted((k for k in set(required) if evidence.get(k) is not True))
    return {'ready': not failed, 'failed': failed}

def drift_report(baseline, current, tolerance):
    if set(baseline) != set(current) or tolerance < 0:
        raise ValueError('metrics')
    return sorted((k for k in baseline if abs(current[k] - baseline[k]) > tolerance))
