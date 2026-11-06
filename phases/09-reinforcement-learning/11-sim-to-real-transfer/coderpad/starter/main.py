"""Original interview practice for 09-reinforcement-learning/11-sim-to-real-transfer.

Local source: phases/09-reinforcement-learning/11-sim-to-real-transfer/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def drift_report(baseline, current, tolerance):
    """baseline/current map identical metric keys to finite numbers. tolerance>=0. Return sorted keys with abs(current-baseline)>tolerance. Missing/additional keys or negative tolerance raises ValueError. Equality with tolerance is allowed."""
    raise NotImplementedError('TODO 1: drift_report; see PROMPT.md')

def zscore_flags(values, threshold):
    """Use population mean/variance from values; flag abs(z)>threshold (strict). Constant or empty lists yield all False/empty. Negative threshold raises ValueError."""
    raise NotImplementedError('TODO 2: zscore_flags; see PROMPT.md')
