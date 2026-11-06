"""Original interview practice for 19-capstone-projects/80-checkpoint-sharded-resume.

Local source: phases/19-capstone-projects/80-checkpoint-sharded-resume/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def manifest(files):
    """files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk."""
    raise NotImplementedError('TODO 1: manifest; see PROMPT.md')

def shard_bounds(total, workers):
    """Require exact ints total>=0 and workers>0. Return workers half-open [start,end] ranges covering 0..total without gaps; allocate one extra item to each earliest worker until the remainder is exhausted. Empty shards are allowed."""
    raise NotImplementedError('TODO 2: shard_bounds; see PROMPT.md')
