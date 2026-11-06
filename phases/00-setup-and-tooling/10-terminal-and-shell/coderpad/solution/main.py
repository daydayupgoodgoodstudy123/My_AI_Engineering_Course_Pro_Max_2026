"""Original interview practice for 00-setup-and-tooling/10-terminal-and-shell.

Local source: phases/00-setup-and-tooling/10-terminal-and-shell/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def command_review(argv, allowlist):
    return isinstance(argv, list) and bool(argv) and all((isinstance(x, str) for x in argv)) and (argv in allowlist)

def contained_path(root, relative):
    if not root.startswith('/') or relative.startswith('/'):
        raise ValueError('path')
    parts = []
    for part in relative.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            if not parts:
                raise ValueError('escape')
            parts.pop()
        else:
            parts.append(part)
    return root.rstrip('/') + ('/' + '/'.join(parts) if parts else '') or '/'
