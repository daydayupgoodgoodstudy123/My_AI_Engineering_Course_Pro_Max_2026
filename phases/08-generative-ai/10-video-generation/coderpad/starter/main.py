"""Original interview practice for 08-generative-ai/10-video-generation.

Local source: phases/08-generative-ai/10-video-generation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def sample_frames(length, count):
    """Require exact nonnegative integers length/count and count<=length. Return count indices spanning 0..length-1 using floor(i*(length-1)/(count-1)). count=0 -> []; count=1 -> [0]. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 1: sample_frames; see PROMPT.md')

def flow_step(state, velocity, delta):
    """Return state+delta*velocity coordinatewise. Require equal lengths and numeric delta in [0,1]; otherwise ValueError. Empty vectors are valid."""
    raise NotImplementedError('TODO 2: flow_step; see PROMPT.md')
