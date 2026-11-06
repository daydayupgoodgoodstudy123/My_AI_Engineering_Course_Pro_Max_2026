"""Original interview practice for 20-recursive-self-improvement/15-reward-hacking-case-files.

Local source: phases/20-recursive-self-improvement/15-reward-hacking-case-files/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def unsupported_claims(claims, evidence_ids):
    """Claims have unique id(str) and references(list of evidence ids). Return sorted claim ids lacking references or containing any unknown reference. Duplicate claim ids raises ValueError. Having a reference verifies linkage only, not factual truth."""
    raise NotImplementedError('TODO 1: unsupported_claims; see PROMPT.md')

def manifest(files):
    """files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk."""
    raise NotImplementedError('TODO 2: manifest; see PROMPT.md')
