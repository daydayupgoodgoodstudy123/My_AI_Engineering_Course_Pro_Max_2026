"""Original interview practice for 00-setup-and-tooling/07-docker-for-ai.

Local source: phases/00-setup-and-tooling/07-docker-for-ai/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def manifest(files):
    if any((p.startswith('/') or '..' in p.split('/') for p in files)):
        raise ValueError('path')
    return {p: hashlib.sha256(files[p].encode()).hexdigest() for p in sorted(files)}

def command_review(argv, allowlist):
    return isinstance(argv, list) and bool(argv) and all((isinstance(x, str) for x in argv)) and (argv in allowlist)
