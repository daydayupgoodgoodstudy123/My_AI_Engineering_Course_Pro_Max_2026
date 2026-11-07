"""Genuine varying-probability requests; independent mathematical full-report expectations outside timing."""
from decimal import Decimal
from fractions import Fraction
import random
from .models import FamilySpec,ReadExposure,JuryConfig,JuryRequest,DrawTicket,SeatVote,SampleTally,CostBreakdown,TrialReport,BatchReport
def base_config(uid='jury',probability=Fraction(1,3),seats=3):
    family=FamilySpec('model-family',probability,seats,100)
    return JuryConfig(uid,(family,),(ReadExposure('read-1','model-family#1','model-family#0',80),ReadExposure('read-2','model-family#2','model-family#0',70)),Decimal('0.000002'),Decimal('0.000001'))
def replay_fixture(count=128,seed=9281):
    requests=tuple(JuryRequest('trial-'+str(i),base_config('probability-'+str(i),Fraction(100003+6007*i,1000003)))for i in range(count))
    rng=random.Random(seed);trials=[]
    for ordinal,request in enumerate(requests):
        config=request.config;family=config.families[0];p=family.probability;roll=rng.randrange(p.denominator);outcome='RIGHT'if Fraction(roll,p.denominator)<p else'WRONG'
        ticket=DrawTicket(ordinal,family.uid,p.numerator,p.denominator,roll);votes=tuple(SeatVote(family.uid+'#'+str(i),family.uid,ordinal,outcome)for i in range(3))
        cost=CostBreakdown(Decimal('0.000600'),Decimal('0.000150'),Decimal('0.000750'),config.reads)
        trials.append(TrialReport(request.trial_id,config,(ticket,),votes,((family.uid,outcome),),SampleTally(3 if outcome=='RIGHT'else 0,3,outcome=='RIGHT'),cost))
    trials=tuple(trials);expected=BatchReport(requests,trials,sum(t.tally.passed for t in trials),Decimal('0.000600')*count,Decimal('0.000150')*count,Decimal('0.000750')*count)
    return requests,seed,expected
