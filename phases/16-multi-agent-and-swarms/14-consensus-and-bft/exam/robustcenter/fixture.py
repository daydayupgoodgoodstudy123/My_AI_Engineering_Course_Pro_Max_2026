"""Complete deterministic probe workload; expected confidence-pair sum is independently closed-form."""
from decimal import Decimal
from fractions import Fraction
from .models import Proposal,Probe,Ballot,NumericKey,ClusterSupport,LegacyScore,Inspection
def ballot(uid,answer,confidence,self_confidence=Fraction(1,3),kind='ANSWER',evaluator='local-calibrator'):
    return Ballot(Proposal(uid,'agent-'+uid,kind,answer,Fraction(self_confidence)),Probe(uid,'probe-'+uid,Fraction(confidence),evaluator,'declared fixture probe'))
def inspection_fixture(count=2400):
    ballots=tuple(ballot(str(i),'4.2%',i%2)for i in range(count));key=NumericKey(Decimal('4.2'),'percent');ones=count//2;zeros=count-ones
    expected=Inspection(ballots,tuple((b.proposal.uid,key)for b in ballots),ClusterSupport(((key,Fraction(ones)),),Fraction(ones),key,()),(LegacyScore(key,Fraction()),),Fraction(ones*zeros),True)
    return ballots,Fraction(2,3),Fraction(count),expected
