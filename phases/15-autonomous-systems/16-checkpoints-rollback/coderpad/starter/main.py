"""Original interview practice for 15-autonomous-systems/16-checkpoints-rollback.

Local source: phases/15-autonomous-systems/16-checkpoints-rollback/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def manifest(files):
    """files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk."""
    raise NotImplementedError('TODO 1: manifest; see PROMPT.md')

def drift_report(baseline, current, tolerance):
    """baseline/current map identical metric keys to finite numbers. tolerance>=0. Return sorted keys with abs(current-baseline)>tolerance. Missing/additional keys or negative tolerance raises ValueError. Equality with tolerance is allowed."""
    raise NotImplementedError('TODO 2: drift_report; see PROMPT.md')
