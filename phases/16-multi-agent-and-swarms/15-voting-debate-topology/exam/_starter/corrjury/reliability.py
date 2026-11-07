"""Exact family Bernoulli kernels, independent-family convolution and strict-majority tail."""
from fractions import Fraction
from .models import FamilyMass,ReliabilityReport
from .support import validate_config
from .primitives import trial_cost
def family_mass_kernel(family):
    """One independent family moves all of its positive seat multiplicity together in an exact two-point law."""
    raise NotImplementedError
def convolve_family_mass(kernels):
    """Convolve independent families into the complete exact correct-seat distribution, retaining zero support entries."""
    raise NotImplementedError
def exact_majority_reliability(config,distribution):
    """Validate complete unit mass, sum strict-majority probability and attach independent declared cost."""
    raise NotImplementedError
