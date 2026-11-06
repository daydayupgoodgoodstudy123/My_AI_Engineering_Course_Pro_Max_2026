"""Original interview practice for 20-recursive-self-improvement/15-reward-hacking-case-files.

Local source: phases/20-recursive-self-improvement/15-reward-hacking-case-files/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def unsupported_claims(claims, evidence_ids):
    if len({c['id'] for c in claims}) != len(claims):
        raise ValueError('duplicate claim')
    known = set(evidence_ids)
    return sorted((c['id'] for c in claims if not c['references'] or not set(c['references']) <= known))

def manifest(files):
    if any((p.startswith('/') or '..' in p.split('/') for p in files)):
        raise ValueError('path')
    return {p: hashlib.sha256(files[p].encode()).hexdigest() for p in sorted(files)}
