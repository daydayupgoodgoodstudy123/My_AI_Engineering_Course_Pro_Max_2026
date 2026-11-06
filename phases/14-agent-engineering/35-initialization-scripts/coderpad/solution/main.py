"""Original interview practice for 14-agent-engineering/35-initialization-scripts.

Local source: phases/14-agent-engineering/35-initialization-scripts/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def environment_report(probes, required):
    missing = sorted(set(required) - set(probes))
    failed = sorted((n for n in set(required) & set(probes) if probes[n]['exit_code'] != 0 or not probes[n]['output'].strip()))
    return {'ready': not missing and (not failed), 'missing': missing, 'failed': failed}

def command_review(argv, allowlist):
    return isinstance(argv, list) and bool(argv) and all((isinstance(x, str) for x in argv)) and (argv in allowlist)
