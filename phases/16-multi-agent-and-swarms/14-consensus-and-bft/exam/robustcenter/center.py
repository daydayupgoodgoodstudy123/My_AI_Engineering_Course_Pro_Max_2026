"""True scalar weighted-median interval, deterministic tie point and separate radius-support audit."""
from fractions import Fraction
from .models import MedianInterval,CenterAudit
from .scalar_support import position_intake,midpoint,evaluate_truth
def weighted_median_interval(points):
    """Return the full minimizer interval over positive exact masses; zero-total is undefined."""
    raise NotImplementedError
def choose_interval_center(interval,policy):
    """Choose the requested lower, upper or exact midpoint of the minimizer interval."""
    raise NotImplementedError
def audit_center_support(points,center,radius,threshold,truth=None):
    """Audit exact positive mass within inclusive radius and ordered minority provenance; truth is independent."""
    raise NotImplementedError
