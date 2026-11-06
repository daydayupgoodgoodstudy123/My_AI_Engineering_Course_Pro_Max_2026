"""Original interview practice for 17-infrastructure-and-production/28-self-hosted-serving-selection.

Local source: phases/17-infrastructure-and-production/28-self-hosted-serving-selection/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def pareto_front(candidates):
    """Candidates have unique id strings, quality higher-is-better, cost lower-is-better. Return sorted ids not dominated by another candidate that is no worse in both and strictly better in at least one. Equal quality/cost entries both survive; empty input yields []."""
    raise NotImplementedError('TODO 1: pareto_front; see PROMPT.md')

def parameter_memory(shapes, bytes_per_parameter):
    """Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError."""
    raise NotImplementedError('TODO 2: parameter_memory; see PROMPT.md')
