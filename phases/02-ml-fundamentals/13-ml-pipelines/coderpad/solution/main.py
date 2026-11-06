"""Original interview practice for 02-ml-fundamentals/13-ml-pipelines.

Local source: phases/02-ml-fundamentals/13-ml-pipelines/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def standardize(train, values):
    if not train:
        raise ValueError('empty train')
    mean = sum(train) / len(train)
    scale = math.sqrt(sum(((x - mean) ** 2 for x in train)) / len(train)) or 1
    return {'mean': mean, 'scale': scale, 'values': [(x - mean) / scale for x in values]}

def split_records(records, train_count, validation_count):
    if any((type(x) is not int or x < 0 for x in (train_count, validation_count))) or train_count + validation_count > len(records):
        raise ValueError('split')
    return {'train': records[:train_count], 'validation': records[train_count:train_count + validation_count], 'test': records[train_count + validation_count:]}
