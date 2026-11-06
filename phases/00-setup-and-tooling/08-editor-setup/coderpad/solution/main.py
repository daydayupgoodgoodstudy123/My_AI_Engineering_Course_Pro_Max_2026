"""Original interview practice for 00-setup-and-tooling/08-editor-setup.

Local source: phases/00-setup-and-tooling/08-editor-setup/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def environment_report(probes, required):
    missing = sorted(set(required) - set(probes))
    failed = sorted((n for n in set(required) & set(probes) if probes[n]['exit_code'] != 0 or not probes[n]['output'].strip()))
    return {'ready': not missing and (not failed), 'missing': missing, 'failed': failed}

def validate_config(config, required, optional):
    missing = sorted(set(required) - set(config))
    unknown = sorted(set(config) - set(required) - set(optional))
    return {'missing': missing, 'unknown': unknown, 'valid': not missing and (not unknown)}
