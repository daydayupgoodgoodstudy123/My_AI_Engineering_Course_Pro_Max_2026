"""Complete exact decimal primitives, comparable-unit intake and independent truth evaluation."""
from decimal import Decimal
from fractions import Fraction
from .models import WeightedPosition
def decimal_exact(value):
    value=Fraction(value);sign=int(value<0);n=abs(value.numerator);d=value.denominator;twos=fives=0
    while d%2==0:twos+=1;d//=2
    while d%5==0:fives+=1;d//=5
    if d!=1:raise ValueError('finite decimal result required')
    scale=max(twos,fives);n*=2**(scale-twos)*5**(scale-fives)
    return Decimal((sign,tuple(map(int,str(n))),-scale))
def midpoint(low,high):return decimal_exact((Fraction(low)+Fraction(high))/2)
def position_intake(points):
    points=tuple(points);units={p.unit for p in points}
    if len(units)>1 or any(not p.value.is_finite()or p.weight<0 for p in points):raise ValueError('comparable finite nonnegative-mass positions required')
    return points
def positions_from_inspection(inspection):
    """P1 produces corrected keys; P2 restores each actual independent Probe field."""
    keys=dict(inspection.canonical)
    return tuple(WeightedPosition(b.proposal.uid,keys[b.proposal.uid].value,keys[b.proposal.uid].unit,b.probe.confidence)for b in inspection.ballots if keys[b.proposal.uid]is not None)
def evaluate_truth(center,unit,truth,radius):
    """Independent supplied truth is separate from acceptance; absent truth stays unknown."""
    if truth is None:return None
    return unit==truth.unit and abs(Fraction(center)-Fraction(truth.value))<=radius
