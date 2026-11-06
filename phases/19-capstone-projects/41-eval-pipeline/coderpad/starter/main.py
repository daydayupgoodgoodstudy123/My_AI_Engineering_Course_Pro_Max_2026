"""Original interview practice for 19-capstone-projects/41-eval-pipeline.

Local source: phases/19-capstone-projects/41-eval-pipeline/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def classification(expected, predicted):
    """Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError."""
    raise NotImplementedError('TODO 1: classification; see PROMPT.md')

def calibration_error(confidences, correct, bins):
    """Equal-length nonempty lists: confidence in [0,1], correct exact bool; bins exact positive int. Bin index=min(bins-1,floor(confidence*bins)). Return sum(bin_size/n*abs(mean confidence-bin accuracy)); invalid inputs raise ValueError."""
    raise NotImplementedError('TODO 2: calibration_error; see PROMPT.md')
