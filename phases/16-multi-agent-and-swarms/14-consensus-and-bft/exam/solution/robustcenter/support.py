"""Complete finite lexical intake, cluster-equivalence consumer and source-style legacy scorer."""
from decimal import Decimal
from fractions import Fraction
from statistics import median
import re
from .models import Ballot,NumericKey,LegacyScore
def numeric_parts(answer):
    """Finite signed decimal with . or comma, optional percent/%; no general NLP or exponent syntax."""
    match=re.fullmatch(r'\s*([+-]?\d+(?:[.,]\d+)?)\s*(%|percent)?\s*',answer,re.I)
    if match is None:raise ValueError('declared scalar answer required')
    return match.group(1).replace(',','.'),'percent' if match.group(2)else 'scalar'
def ballot_intake(ballots,threshold):
    ballots=tuple(ballots)
    if not Fraction(0)<threshold<=1:raise ValueError('threshold in (0,1] required')
    ids=set()
    for ballot in ballots:
        if type(ballot)is not Ballot or ballot.proposal.uid in ids:raise ValueError('unique typed ballots required')
        ids.add(ballot.proposal.uid)
        p=ballot.proposal;q=ballot.probe
        if q.proposal_uid!=p.uid or not(0<=p.self_confidence<=1 and 0<=q.confidence<=1):raise ValueError('bound declared confidence records required')
        if p.kind=='ANSWER':numeric_parts(p.answer)
        elif p.kind!='ABSTAIN' or p.answer is not None:raise ValueError('explicit ANSWER or ABSTAIN required')
    return ballots
def require_equivalent(ballot,key):
    number,unit=numeric_parts(ballot.proposal.answer)
    if key!=NumericKey(Decimal(number),unit):raise ValueError('cluster scalar and unit disagree with its declared member')
def validate_cluster_members(groups):
    for key,members in groups.items():
        if key is not None:
            for ballot in members:require_equivalent(ballot,key)
def legacy_cluster_scores(groups):
    """Given source confidence-space heuristic, not an answer-position center."""
    rows=[]
    for key,members in groups.items():
        if key is None:continue
        values=[b.probe.confidence for b in members];middle=median(values)
        spread=sum((abs(value-middle)for value in values),Fraction())
        rows.append(LegacyScore(key,len(members)*max(Fraction(),1-spread)))
    return tuple(rows)
