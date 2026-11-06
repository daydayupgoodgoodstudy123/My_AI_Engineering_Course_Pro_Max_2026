"""Case-paired bootstrap of criterion and stratified category score changes."""
import math,random
from .contracts import Interval,Comparison,indexed_observations,score_number,statistics_parameters
def _interval(values,samples,confidence,seed):
    """Resample complete scalar case differences, with replacement and a local RNG.

    For B sorted bootstrap means, endpoints are floor(alpha*B) and
    floor((1-alpha)*B)-1, each clamped to [0,B-1], alpha=(1-confidence)/2.
    The upper index is at least the lower index, including small B/confidence.
    Single-case intervals equal that difference; there is no early rounding.
    """
    n=len(values);rng=random.Random(seed);means=[]
    for _ in range(samples):means.append(math.fsum(values[rng.randrange(n)] for _ in range(n))/n)
    means.sort();alpha=(1-confidence)/2
    lo=max(0,min(samples-1,int(alpha*samples)));hi=max(lo,max(0,min(samples-1,int((1-alpha)*samples)-1)))
    return Interval(n,math.fsum(values)/n,means[lo],means[hi])
def compare_paired(baseline,variant,*,samples=1000,confidence=0.95,seed=0,tolerance=0.0):
    """Compare exactly matching case/criterion keys and category assignments.

    Every score must be judged. Criterion groups resample their case differences.
    Overall/category groups first average all matched criterion differences WITHIN
    each case, then resample cases. Each group starts its own Random(seed).
    Block iff any criterion/category interval upper endpoint is below -tolerance;
    an overall gain cannot suppress a category regression. Empty paired runs are
    accepted with no intervals. This teaching decision is no deployment guarantee.
    """
    statistics_parameters(samples,confidence,seed,tolerance)
    b=indexed_observations(baseline);v=indexed_observations(variant)
    if set(b)!=set(v):raise ValueError("paired observation keys differ")
    criterion_values={};case_values={};case_categories={}
    for key in sorted(b):
        left,right=b[key],v[key]
        if left.category!=right.category or left.score_text is None or right.score_text is None:raise ValueError("unpaired category or unjudged score")
        delta=score_number(right.score_text)-score_number(left.score_text)
        criterion_values.setdefault(key[1],[]).append(delta)
        case_values.setdefault(key[0],[]).append(delta);case_categories[key[0]]=left.category
    case_means={case:math.fsum(values)/len(values) for case,values in case_values.items()}
    category_values={}
    for case in sorted(case_means):category_values.setdefault(case_categories[case],[]).append(case_means[case])
    summarize=lambda values:_interval(values,samples,confidence,seed)
    criteria={name:summarize(criterion_values[name]) for name in sorted(criterion_values)}
    categories={name:summarize(category_values[name]) for name in sorted(category_values)}
    overall=summarize([case_means[case] for case in sorted(case_means)]) if case_means else None
    accepted=all(interval.upper>=-tolerance for interval in list(criteria.values())+list(categories.values()))
    return Comparison(overall,criteria,categories,accepted)
