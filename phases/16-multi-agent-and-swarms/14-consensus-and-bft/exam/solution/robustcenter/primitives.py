"""Signed scalar keys, explicit abstentions, confidence-mass admission and pairwise dispersion."""
from decimal import Decimal
from fractions import Fraction
from .models import NumericKey,ClusterSupport
from .support import numeric_parts
def canonicalize_proposal(answer):
    """Return the signed finite scalar and canonical percent/scalar unit."""
    number,unit=numeric_parts(answer)
    return NumericKey(Decimal(number),unit)
def legacy_support_report(groups,threshold):
    """Exclude ABSTAIN from answer mass; accept inclusive confidence-mass threshold, retaining all abstentions."""
    eligible={key:members for key,members in groups.items()if key is not None}
    masses=tuple((key,sum((b.probe.confidence for b in members),Fraction()))for key,members in eligible.items())
    total=sum((mass for key,mass in masses),Fraction())
    winner=max(masses,key=lambda row:row[1])[0]if masses else None
    winning_mass=next((mass for key,mass in masses if key==winner),Fraction())
    accepted=total>0 and winning_mass>=threshold*total
    return ClusterSupport(masses,total,winner if accepted else None,tuple(b.proposal.uid for b in groups.get(None,())))
def pairwise_confidence_disagreement(confidences):
    """Return exact sum of absolute confidence gaps over every unordered pair, with multiplicity."""
    ordered=sorted(confidences);prefix=Fraction();result=Fraction()
    for index,value in enumerate(ordered):
        result+=index*value-prefix;prefix+=value
    return result
