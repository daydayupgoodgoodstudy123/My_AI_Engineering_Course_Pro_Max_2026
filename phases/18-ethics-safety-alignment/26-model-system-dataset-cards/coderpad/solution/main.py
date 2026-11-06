"""Original interview practice for 18-ethics-safety-alignment/26-model-system-dataset-cards.

Local source: phases/18-ethics-safety-alignment/26-model-system-dataset-cards/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def validate_config(config, required, optional):
    missing = sorted(set(required) - set(config))
    unknown = sorted(set(config) - set(required) - set(optional))
    return {'missing': missing, 'unknown': unknown, 'valid': not missing and (not unknown)}

def validate_handoff(bundle):
    issues = [k for k in ('objective', 'state', 'next_action') if not isinstance(bundle.get(k), str) or not bundle[k].strip()]
    checks = bundle.get('checks')
    if not isinstance(checks, list) or not checks or any((not isinstance(x, str) or not x.strip() for x in checks)):
        issues.append('checks')
    return sorted(issues)
