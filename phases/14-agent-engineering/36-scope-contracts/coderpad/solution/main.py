"""Original interview practice for 14-agent-engineering/36-scope-contracts.

Local source: phases/14-agent-engineering/36-scope-contracts/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def validate_config(config, required, optional):
    missing = sorted(set(required) - set(config))
    unknown = sorted(set(config) - set(required) - set(optional))
    return {'missing': missing, 'unknown': unknown, 'valid': not missing and (not unknown)}

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
