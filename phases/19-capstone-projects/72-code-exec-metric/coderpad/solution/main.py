"""Original interview practice for 19-capstone-projects/72-code-exec-metric.

Local source: phases/19-capstone-projects/72-code-exec-metric/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def permission_decision(capability, granted, side_effect, approved):
    if type(side_effect) is not bool or type(approved) is not bool:
        raise ValueError('flags')
    if capability not in granted:
        return 'deny'
    return 'ask' if side_effect and (not approved) else 'allow'

def command_review(argv, allowlist):
    return isinstance(argv, list) and bool(argv) and all((isinstance(x, str) for x in argv)) and (argv in allowlist)
