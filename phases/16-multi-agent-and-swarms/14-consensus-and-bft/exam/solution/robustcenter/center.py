"""True scalar weighted-median interval, deterministic tie point and separate radius-support audit."""
from fractions import Fraction
from .models import MedianInterval,CenterAudit
from .scalar_support import position_intake,midpoint,evaluate_truth
def weighted_median_interval(points):
    """Return the full minimizer interval over positive exact masses; zero-total is undefined."""
    points=position_intake(points);positive=sorted((p for p in points if p.weight>0),key=lambda p:p.value)
    total=sum((p.weight for p in positive),Fraction())
    if total==0:raise ValueError('positive total mass required')
    cumulative=Fraction()
    for index,point in enumerate(positive):
        cumulative+=point.weight
        if 2*cumulative>total:return MedianInterval(point.value,point.value,point.unit)
        if 2*cumulative==total:return MedianInterval(point.value,positive[index+1].value,point.unit)
def choose_interval_center(interval,policy):
    """Choose the requested lower, upper or exact midpoint of the minimizer interval."""
    if policy=='lower':return interval.low
    if policy=='upper':return interval.high
    if policy=='midpoint':return midpoint(interval.low,interval.high)
    raise ValueError('declared tie policy required')
def audit_center_support(points,center,radius,threshold,truth=None):
    """Audit exact positive mass within inclusive radius and ordered minority provenance; truth is independent."""
    points=position_intake(points)
    if radius<0 or not Fraction(0)<threshold<=1:raise ValueError('nonnegative radius and threshold in (0,1] required')
    total=sum((p.weight for p in points),Fraction())
    if total==0:raise ValueError('positive total mass required')
    supporters=tuple(p for p in points if p.weight>0 and abs(Fraction(p.value)-Fraction(center))<=radius)
    support=sum((p.weight for p in supporters),Fraction())
    minority=tuple(p.uid for p in points if p.weight>0 and abs(Fraction(p.value)-Fraction(center))>radius)
    unit=points[0].unit
    return CenterAudit(center,unit,support,total,support>=threshold*total,minority,evaluate_truth(center,unit,truth,radius))
