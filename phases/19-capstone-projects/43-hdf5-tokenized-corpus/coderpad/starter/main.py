"""Original interview practice for 19-capstone-projects/43-hdf5-tokenized-corpus.

Local source: phases/19-capstone-projects/43-hdf5-tokenized-corpus/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def chunk_tokens(tokens, size, overlap):
    """Require exact integers size>0 and 0<=overlap<size. Return windows starting at 0 then advancing size-overlap; include a short final window, stop once a window reaches the end. Empty tokens yields []. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: chunk_tokens; see PROMPT.md')

def manifest(files):
    """files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk."""
    raise NotImplementedError('TODO 2: manifest; see PROMPT.md')
