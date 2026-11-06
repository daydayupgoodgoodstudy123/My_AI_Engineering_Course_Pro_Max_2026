"""Original interview practice for 10-llms-from-scratch/03-data-pipelines.

Local source: phases/10-llms-from-scratch/03-data-pipelines/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def chunk_tokens(tokens, size, overlap):
    if type(size) is not int or type(overlap) is not int or size <= 0 or (not 0 <= overlap < size):
        raise ValueError('window')
    result = []
    start = 0
    while start < len(tokens):
        result.append(tokens[start:start + size])
        if start + size >= len(tokens):
            break
        start += size - overlap
    return result

def split_records(records, train_count, validation_count):
    if any((type(x) is not int or x < 0 for x in (train_count, validation_count))) or train_count + validation_count > len(records):
        raise ValueError('split')
    return {'train': records[:train_count], 'validation': records[train_count:train_count + validation_count], 'test': records[train_count + validation_count:]}
