"""Original interview practice for 19-capstone-projects/42-large-corpus-downloader.

Local source: phases/19-capstone-projects/42-large-corpus-downloader/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def manifest(files):
    """files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk."""
    raise NotImplementedError('TODO 1: manifest; see PROMPT.md')

def retry_delays(attempts, base, cap):
    """Return [min(cap,base*2**i) for i in range(attempts)]. attempts exact int 0..30; base/cap nonnegative numeric. Invalid input raises ValueError. No sleeping, randomness or calls are performed."""
    raise NotImplementedError('TODO 2: retry_delays; see PROMPT.md')
