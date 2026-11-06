"""Original interview practice for 00-setup-and-tooling/09-data-management.

Local source: phases/00-setup-and-tooling/09-data-management/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def split_records(records, train_count, validation_count):
    """Preserve record order. Counts are exact nonnegative ints and their sum cannot exceed input length. Return {'train':prefix,'validation':next records,'test':remainder}. Return copies of list slices; invalid counts raise ValueError."""
    raise NotImplementedError('TODO 1: split_records; see PROMPT.md')

def manifest(files):
    """files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk."""
    raise NotImplementedError('TODO 2: manifest; see PROMPT.md')
