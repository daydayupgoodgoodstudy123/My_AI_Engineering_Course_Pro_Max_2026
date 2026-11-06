"""Original interview practice for 15-autonomous-systems/16-checkpoints-rollback.

Local source: phases/15-autonomous-systems/16-checkpoints-rollback/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def manifest(files):
    if any((p.startswith('/') or '..' in p.split('/') for p in files)):
        raise ValueError('path')
    return {p: hashlib.sha256(files[p].encode()).hexdigest() for p in sorted(files)}

def drift_report(baseline, current, tolerance):
    if set(baseline) != set(current) or tolerance < 0:
        raise ValueError('metrics')
    return sorted((k for k in baseline if abs(current[k] - baseline[k]) > tolerance))
