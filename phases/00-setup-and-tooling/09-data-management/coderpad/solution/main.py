"""Original interview practice for 00-setup-and-tooling/09-data-management.

Local source: phases/00-setup-and-tooling/09-data-management/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def split_records(records, train_count, validation_count):
    if any((type(x) is not int or x < 0 for x in (train_count, validation_count))) or train_count + validation_count > len(records):
        raise ValueError('split')
    return {'train': records[:train_count], 'validation': records[train_count:train_count + validation_count], 'test': records[train_count + validation_count:]}

def manifest(files):
    if any((p.startswith('/') or '..' in p.split('/') for p in files)):
        raise ValueError('path')
    return {p: hashlib.sha256(files[p].encode()).hexdigest() for p in sorted(files)}
