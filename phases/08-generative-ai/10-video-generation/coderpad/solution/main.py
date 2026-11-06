"""Original interview practice for 08-generative-ai/10-video-generation.

Local source: phases/08-generative-ai/10-video-generation/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def sample_frames(length, count):
    if type(length) is not int or type(count) is not int or (not 0 <= count <= length):
        raise ValueError('frames')
    if count == 0:
        return []
    if count == 1:
        return [0]
    return [i * (length - 1) // (count - 1) for i in range(count)]

def flow_step(state, velocity, delta):
    if len(state) != len(velocity) or not 0 <= delta <= 1:
        raise ValueError('contract')
    return [x + delta * v for x, v in zip(state, velocity)]
