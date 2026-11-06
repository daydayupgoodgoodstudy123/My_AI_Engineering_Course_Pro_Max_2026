"""Original interview practice for 00-setup-and-tooling/03-gpu-setup-and-cloud.

Local source: phases/00-setup-and-tooling/03-gpu-setup-and-cloud/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def parameter_memory(shapes, bytes_per_parameter):
    """Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError."""
    raise NotImplementedError('TODO 1: parameter_memory; see PROMPT.md')

def amdahl(serial_fraction, speedup):
    """Return 1/(serial_fraction+(1-serial_fraction)/speedup). Require serial_fraction in [0,1] and speedup>=1; otherwise ValueError. This models latency, not queueing throughput."""
    raise NotImplementedError('TODO 2: amdahl; see PROMPT.md')
