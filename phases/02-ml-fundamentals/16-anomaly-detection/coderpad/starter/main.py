"""Original interview practice for 02-ml-fundamentals/16-anomaly-detection.

Local source: phases/02-ml-fundamentals/16-anomaly-detection/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def zscore_flags(values, threshold):
    """Use population mean/variance from values; flag abs(z)>threshold (strict). Constant or empty lists yield all False/empty. Negative threshold raises ValueError."""
    raise NotImplementedError('TODO 1: zscore_flags; see PROMPT.md')

def summary(values):
    """Return {'mean':arithmetic mean,'variance':population variance,'min':minimum,'max':maximum} for a nonempty numeric list. Empty input raises ValueError."""
    raise NotImplementedError('TODO 2: summary; see PROMPT.md')
