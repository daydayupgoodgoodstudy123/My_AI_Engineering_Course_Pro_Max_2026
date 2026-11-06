"""Original interview practice for 04-computer-vision/03-cnns-lenet-to-resnet.

Local source: phases/04-computer-vision/03-cnns-lenet-to-resnet/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def parameter_memory(shapes, bytes_per_parameter):
    if type(bytes_per_parameter) is not int or bytes_per_parameter <= 0 or any((type(d) is not int or d <= 0 for shape in shapes for d in shape)):
        raise ValueError('shape')
    return sum((math.prod(shape) for shape in shapes)) * bytes_per_parameter

def convolve(signal, kernel, stride=1):
    if not kernel or type(stride) is not int or stride <= 0:
        raise ValueError('window')
    return [sum((a * b for a, b in zip(signal[i:i + len(kernel)], kernel))) for i in range(0, len(signal) - len(kernel) + 1, stride)]
