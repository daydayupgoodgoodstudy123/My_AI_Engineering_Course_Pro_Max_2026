"""Original interview practice for 02-ml-fundamentals/13-ml-pipelines.

Local source: phases/02-ml-fundamentals/13-ml-pipelines/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def standardize(train, values):
    """Compute mean and population standard deviation from nonempty train, then transform values. If training variance is zero use scale=1. Return {'mean','scale','values'}. Never fit on values; empty train raises ValueError."""
    raise NotImplementedError('TODO 1: standardize; see PROMPT.md')

def split_records(records, train_count, validation_count):
    """Preserve record order. Counts are exact nonnegative ints and their sum cannot exceed input length. Return {'train':prefix,'validation':next records,'test':remainder}. Return copies of list slices; invalid counts raise ValueError."""
    raise NotImplementedError('TODO 2: split_records; see PROMPT.md')
