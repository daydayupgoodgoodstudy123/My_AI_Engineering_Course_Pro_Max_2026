"""Original interview practice for 04-computer-vision/03-cnns-lenet-to-resnet.

Local source: phases/04-computer-vision/03-cnns-lenet-to-resnet/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def parameter_memory(shapes, bytes_per_parameter):
    """Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError."""
    raise NotImplementedError('TODO 1: parameter_memory; see PROMPT.md')

def convolve(signal, kernel, stride=1):
    """Compute valid 1D cross-correlation (kernel is NOT reversed) using exact positive integer stride. Empty kernel or invalid stride raises ValueError. Kernel longer than signal yields []."""
    raise NotImplementedError('TODO 2: convolve; see PROMPT.md')
