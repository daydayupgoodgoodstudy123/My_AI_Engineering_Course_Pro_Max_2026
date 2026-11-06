"""Original interview practice for 19-capstone-projects/83-prompt-injection-detector.

Local source: phases/19-capstone-projects/83-prompt-injection-detector/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import re

def tokenize(text):
    return re.findall('[a-z0-9]+', text.casefold())

def unsupported_claims(claims, evidence_ids):
    if len({c['id'] for c in claims}) != len(claims):
        raise ValueError('duplicate claim')
    known = set(evidence_ids)
    return sorted((c['id'] for c in claims if not c['references'] or not set(c['references']) <= known))
