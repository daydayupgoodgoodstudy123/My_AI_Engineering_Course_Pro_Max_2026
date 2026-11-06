"""Case-paired bootstrap of criterion and stratified category score changes."""
import math,random
from .contracts import Interval,Comparison,indexed_observations,score_number,statistics_parameters
def _interval(values,samples,confidence,seed):
    """Resample complete scalar case differences, with replacement and a local RNG.

    For B sorted bootstrap means, endpoints are floor(alpha*B) and
    floor((1-alpha)*B)-1, each clamped to [0,B-1], alpha=(1-confidence)/2.
    The upper index is at least the lower index, including small B/confidence.
    Single-case intervals equal that difference; there is no early rounding.
    """
    raise NotImplementedError
def compare_paired(baseline,variant,*,samples=1000,confidence=0.95,seed=0,tolerance=0.0):
    """Compare exactly matching case/criterion keys and category assignments.

    Every score must be judged. Criterion groups resample their case differences.
    Overall/category groups first average all matched criterion differences WITHIN
    each case, then resample cases. Each group starts its own Random(seed).
    Block iff any criterion/category interval upper endpoint is below -tolerance;
    an overall gain cannot suppress a category regression. Empty paired runs are
    accepted with no intervals. This teaching decision is no deployment guarantee.
    """
    raise NotImplementedError
