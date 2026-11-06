"""Original interview practice for 06-speech-and-audio/17-audio-evaluation-metrics.

Local source: phases/06-speech-and-audio/17-audio-evaluation-metrics/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def edit_distance(reference, hypothesis):
    """Return Levenshtein distance between two token lists, using unit insertion/deletion/substitution costs. Inputs are lists of scalar tokens. Empty sequences are valid; no transposition operation."""
    raise NotImplementedError('TODO 1: edit_distance; see PROMPT.md')

def calibration_error(confidences, correct, bins):
    """Equal-length nonempty lists: confidence in [0,1], correct exact bool; bins exact positive int. Bin index=min(bins-1,floor(confidence*bins)). Return sum(bin_size/n*abs(mean confidence-bin accuracy)); invalid inputs raise ValueError."""
    raise NotImplementedError('TODO 2: calibration_error; see PROMPT.md')
