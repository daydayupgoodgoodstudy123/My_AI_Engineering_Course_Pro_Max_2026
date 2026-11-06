"""Original interview practice for 18-ethics-safety-alignment/21-fairness-criteria-group-individual-counterfactual.

Local source: phases/18-ethics-safety-alignment/21-fairness-criteria-group-individual-counterfactual/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
from collections import Counter

def selection_gap(groups, selected):
    """Equal-length nonempty lists; groups are strings and selected exact booleans. Return {'rates':group->selected_count/group_count,'gap':max(rate)-min(rate)}. Invalid length/labels raises ValueError. This is descriptive demographic-parity evidence, not a complete fairness judgment."""
    raise NotImplementedError('TODO 1: selection_gap; see PROMPT.md')

def calibration_error(confidences, correct, bins):
    """Equal-length nonempty lists: confidence in [0,1], correct exact bool; bins exact positive int. Bin index=min(bins-1,floor(confidence*bins)). Return sum(bin_size/n*abs(mean confidence-bin accuracy)); invalid inputs raise ValueError."""
    raise NotImplementedError('TODO 2: calibration_error; see PROMPT.md')
