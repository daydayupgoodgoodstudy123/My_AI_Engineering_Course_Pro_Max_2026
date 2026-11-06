"""Original interview practice for 00-setup-and-tooling/01-dev-environment.

Local source: phases/00-setup-and-tooling/01-dev-environment/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import re

def environment_report(probes, required):
    missing = sorted(set(required) - set(probes))
    failed = sorted((n for n in set(required) & set(probes) if probes[n]['exit_code'] != 0 or not probes[n]['output'].strip()))
    return {'ready': not missing and (not failed), 'missing': missing, 'failed': failed}

def compatible_version(version, minimum, maximum_major):
    if type(maximum_major) is not int or maximum_major < 0:
        raise ValueError('major')

    def parse(s):
        if not isinstance(s, str) or re.fullmatch('[0-9]+\\.[0-9]+\\.[0-9]+', s) is None:
            raise ValueError('version')
        return tuple((int(x) for x in s.split('.')))
    v, m = (parse(version), parse(minimum))
    return v >= m and v[0] <= maximum_major
