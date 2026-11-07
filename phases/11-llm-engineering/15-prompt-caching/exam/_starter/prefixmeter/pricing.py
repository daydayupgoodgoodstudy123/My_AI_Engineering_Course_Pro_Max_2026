"""Exact source-role billing, observed storage integration and strict integer break-even."""
from fractions import Fraction
from .contracts import CostReport,rational,validate_price,validate_money
def price_collection(collection,prices):
    """Price repaired P1 facts using declared illustrative per-1K token rate roles.

    WRITE/READ/UNCACHED prefix uses write/read/base; every changing suffix uses
    base. Each unique lifetime contributes tokens*observed_microseconds to storage
    at per-1K-token-hour units. Repaired collection already owns all lifetimes and
    the correct cutoff; do not reimplement TTL or count reads as storage objects.
    Use exact rational arithmetic, no intermediate rounding. Return global and
    per-profile input/storage/total/baseline; savings0 for baseline0. Primitive
    exact rate parsing is given; no completed charge or inverse helper is supplied.
    """
    raise NotImplementedError
def break_even_reads(base,write,read,storage):
    """Minimal additional integer reads n>=0 satisfying W+nR+S < (n+1)B.

    Inputs are exact nonnegative Fraction money for one declared prefix/write
    window, not raw per-token rates. Return None if strict savings is impossible.
    Suffix costs cancel only in this inverse comparison, never in full billing.
    """
    raise NotImplementedError
