"""Original interview practice for 19-capstone-projects/06-devops-troubleshooting-agent.

Local source: phases/19-capstone-projects/06-devops-troubleshooting-agent/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def environment_report(probes, required):
    missing = sorted(set(required) - set(probes))
    failed = sorted((n for n in set(required) & set(probes) if probes[n]['exit_code'] != 0 or not probes[n]['output'].strip()))
    return {'ready': not missing and (not failed), 'missing': missing, 'failed': failed}

def topological_order(dependencies):
    pending = {n: set(ds) for n, ds in dependencies.items()}
    for ds in dependencies.values():
        for name in ds:
            pending.setdefault(name, set())
    result = []
    while pending:
        ready = sorted((n for n, ds in pending.items() if not ds))
        if not ready:
            raise ValueError('cycle')
        n = ready[0]
        result.append(n)
        del pending[n]
        for ds in pending.values():
            ds.discard(n)
    return result
