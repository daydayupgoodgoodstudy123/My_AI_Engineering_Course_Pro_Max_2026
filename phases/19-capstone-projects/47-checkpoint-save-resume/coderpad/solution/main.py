"""Original interview practice for 19-capstone-projects/47-checkpoint-save-resume.

Local source: phases/19-capstone-projects/47-checkpoint-save-resume/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def manifest(files):
    if any((p.startswith('/') or '..' in p.split('/') for p in files)):
        raise ValueError('path')
    return {p: hashlib.sha256(files[p].encode()).hexdigest() for p in sorted(files)}

def transition(state, target):
    edges = {'queued': {'running', 'canceled'}, 'running': {'waiting', 'completed', 'failed', 'canceled'}, 'waiting': {'running', 'canceled'}}
    if target not in edges.get(state, set()):
        raise ValueError('transition')
    return target
