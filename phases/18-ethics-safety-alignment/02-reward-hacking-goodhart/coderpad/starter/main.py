"""Original interview practice for 18-ethics-safety-alignment/02-reward-hacking-goodhart.

Local source: phases/18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def drift_report(baseline, current, tolerance):
    """baseline/current map identical metric keys to finite numbers. tolerance>=0. Return sorted keys with abs(current-baseline)>tolerance. Missing/additional keys or negative tolerance raises ValueError. Equality with tolerance is allowed."""
    raise NotImplementedError('TODO 1: drift_report; see PROMPT.md')

def classification(expected, predicted):
    """Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError."""
    raise NotImplementedError('TODO 2: classification; see PROMPT.md')
