"""Exact family Bernoulli kernels, independent-family convolution and strict-majority tail."""
from fractions import Fraction
from .models import FamilyMass,ReliabilityReport
from .support import validate_config
from .primitives import trial_cost
def family_mass_kernel(family):
    """One independent family moves all of its positive seat multiplicity together in an exact two-point law."""
    mass=[Fraction()]*(family.seats+1);mass[0]=1-family.probability;mass[family.seats]=family.probability
    return FamilyMass(family.uid,family.seats,tuple(mass))
def convolve_family_mass(kernels):
    """Convolve independent families into the complete exact correct-seat distribution, retaining zero support entries."""
    distribution=(Fraction(1),)
    for kernel in kernels:
        updated=[Fraction()]*(len(distribution)+kernel.seats)
        for left,p_left in enumerate(distribution):
            for right,p_right in enumerate(kernel.mass):updated[left+right]+=p_left*p_right
        distribution=tuple(updated)
    return distribution
def exact_majority_reliability(config,distribution):
    """Validate complete unit mass, sum strict-majority probability and attach independent declared cost."""
    validate_config(config);total=sum(f.seats for f in config.families);distribution=tuple(distribution)
    if len(distribution)!=total+1 or any(type(p)is not Fraction or p<0 for p in distribution)or sum(distribution,Fraction())!=1:raise ValueError('complete exact unit-mass distribution required')
    threshold=total//2+1;probability=sum(distribution[threshold:],Fraction())
    return ReliabilityReport(config.uid,total,threshold,distribution,probability,trial_cost(config))
