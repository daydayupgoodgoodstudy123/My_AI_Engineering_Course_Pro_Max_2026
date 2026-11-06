"""Original interview practice for 19-capstone-projects/42-large-corpus-downloader.

Local source: phases/19-capstone-projects/42-large-corpus-downloader/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def manifest(files):
    if any((p.startswith('/') or '..' in p.split('/') for p in files)):
        raise ValueError('path')
    return {p: hashlib.sha256(files[p].encode()).hexdigest() for p in sorted(files)}

def retry_delays(attempts, base, cap):
    if type(attempts) is not int or not 0 <= attempts <= 30 or base < 0 or (cap < 0):
        raise ValueError('retry')
    return [min(cap, base * 2 ** i) for i in range(attempts)]
