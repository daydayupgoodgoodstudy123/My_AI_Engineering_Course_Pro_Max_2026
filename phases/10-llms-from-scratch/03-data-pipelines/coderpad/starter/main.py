"""Original interview practice for 10-llms-from-scratch/03-data-pipelines.

Local source: phases/10-llms-from-scratch/03-data-pipelines/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def chunk_tokens(tokens, size, overlap):
    """Require exact integers size>0 and 0<=overlap<size. Return windows starting at 0 then advancing size-overlap; include a short final window, stop once a window reaches the end. Empty tokens yields []. Invalid configuration raises ValueError."""
    raise NotImplementedError('TODO 1: chunk_tokens; see PROMPT.md')

def split_records(records, train_count, validation_count):
    """Preserve record order. Counts are exact nonnegative ints and their sum cannot exceed input length. Return {'train':prefix,'validation':next records,'test':remainder}. Return copies of list slices; invalid counts raise ValueError."""
    raise NotImplementedError('TODO 2: split_records; see PROMPT.md')
