"""Original interview practice for 02-ml-fundamentals/01-what-is-machine-learning.

Local source: phases/02-ml-fundamentals/01-what-is-machine-learning/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def split_records(records, train_count, validation_count):
    if any((type(x) is not int or x < 0 for x in (train_count, validation_count))) or train_count + validation_count > len(records):
        raise ValueError('split')
    return {'train': records[:train_count], 'validation': records[train_count:train_count + validation_count], 'test': records[train_count + validation_count:]}

def classification(expected, predicted):
    if len(expected) != len(predicted) or any((type(x) is not bool for x in expected + predicted)):
        raise ValueError('labels')
    tp = sum((a and b for a, b in zip(expected, predicted)))
    fp = sum((not a and b for a, b in zip(expected, predicted)))
    fn = sum((a and (not b) for a, b in zip(expected, predicted)))
    tn = len(expected) - tp - fp - fn
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'precision': p, 'recall': r, 'f1': 2 * p * r / (p + r) if p + r else 0}
