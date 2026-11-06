"""Original interview practice for 00-setup-and-tooling/05-jupyter-notebooks.

Local source: phases/00-setup-and-tooling/05-jupyter-notebooks/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def profile(events):
    """Events have name,start,end numeric milliseconds. Reject end<start with ValueError. Return name->{'count','total','max'} aggregated over individual durations. Empty input -> {}; overlapping durations are summed, not wall-clock latency."""
    raise NotImplementedError('TODO 1: profile; see PROMPT.md')

def summary(values):
    """Return {'mean':arithmetic mean,'variance':population variance,'min':minimum,'max':maximum} for a nonempty numeric list. Empty input raises ValueError."""
    raise NotImplementedError('TODO 2: summary; see PROMPT.md')
