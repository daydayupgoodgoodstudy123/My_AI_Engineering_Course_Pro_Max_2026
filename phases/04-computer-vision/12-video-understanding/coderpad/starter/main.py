"""Original interview practice for 04-computer-vision/12-video-understanding.

Local source: phases/04-computer-vision/12-video-understanding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def sample_frames(length, count):
    """Require exact nonnegative integers length/count and count<=length. Return count indices spanning 0..length-1 using floor(i*(length-1)/(count-1)). count=0 -> []; count=1 -> [0]. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 1: sample_frames; see PROMPT.md')

def audio_frames(samples, width, hop):
    """width and hop are exact positive ints. Return complete windows only, starting at 0,hop,2*hop...; drop incomplete tail. Short or empty signals yield []. Invalid size raises ValueError."""
    raise NotImplementedError('TODO 2: audio_frames; see PROMPT.md')
