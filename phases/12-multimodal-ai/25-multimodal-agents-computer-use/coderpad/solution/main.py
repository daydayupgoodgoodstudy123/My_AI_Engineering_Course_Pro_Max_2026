"""Original interview practice for 12-multimodal-ai/25-multimodal-agents-computer-use.

Local source: phases/12-multimodal-ai/25-multimodal-agents-computer-use/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def permission_decision(capability, granted, side_effect, approved):
    if type(side_effect) is not bool or type(approved) is not bool:
        raise ValueError('flags')
    if capability not in granted:
        return 'deny'
    return 'ask' if side_effect and (not approved) else 'allow'

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
