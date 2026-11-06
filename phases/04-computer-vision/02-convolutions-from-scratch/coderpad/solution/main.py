"""Original interview practice for 04-computer-vision/02-convolutions-from-scratch.

Local source: phases/04-computer-vision/02-convolutions-from-scratch/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def convolve(signal, kernel, stride=1):
    if not kernel or type(stride) is not int or stride <= 0:
        raise ValueError('window')
    return [sum((a * b for a, b in zip(signal[i:i + len(kernel)], kernel))) for i in range(0, len(signal) - len(kernel) + 1, stride)]

def max_pool(values, width):
    if type(width) is not int or width <= 0:
        raise ValueError('width')
    return [max(values[i:i + width]) for i in range(0, len(values), width)]
