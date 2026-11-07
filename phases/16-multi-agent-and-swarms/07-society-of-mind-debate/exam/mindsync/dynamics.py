"""Candidate weighted revision, source confidence/history commit and fixed rounds."""
from fractions import Fraction
from .intake import new_agents,frozen_round,requested_rounds
from .service import RoundDesk

def revise_agent(own,others):
    """Compute confidence-weighted own-plus-all-others answer from a frozen vector.

    Inputs are finite binary64 answers and confidences in[0,1]. Reject total
    weight0. Accumulation must preserve representable mixed-scale residuals and
    avoid overflow before the final finite convex mean is rounded to binary64.
    This is numeric toy arithmetic, not a probability or truth guarantee.
    """
    raise NotImplementedError

def commit_numeric_round(agents,snapshot):
    """Commit each frozen-round weighted answer, own capped confidence and new history."""
    raise NotImplementedError

def run_numeric_debate(initial,rounds,truth=None,tol=0.1):
    """Initialize once, retain round0, and commit exactly the requested extra rounds.

    The correct supplied frozen snapshot follows the lesson prose; live object
    aliasing in source main is not a candidate defect. Do not stop on agreement
    or truth, add an alpha/topology, or infer quality from the scripted dynamics.
    """
    raise NotImplementedError
