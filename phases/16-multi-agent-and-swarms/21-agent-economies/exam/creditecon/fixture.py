"""Given: real criterion-valued games and genuine complete-permutation prefix requests."""
from fractions import Fraction
from random import Random
from .models import Game,Criterion,UtilityReceipt,ReplayReport

def workload(count=2400):
    players=tuple('abcd');criteria=tuple(Criterion('rule'+str(i),frozenset(p for j,p in enumerate(players)if (i%64)&(1<<j)),Fraction((i%13)-5,1+i%7))for i in range(1024))
    game=Game('criterion-market',players,Fraction(7,3),criteria)
    rng=Random(41);requests=[]
    for _ in range(count):
        order=list(players);rng.shuffle(order);prefix=[];requests.append(frozenset())
        for p in order:prefix.append(p);requests.append(frozenset(prefix))
    return game,tuple(requests)

def expected_replay(game,requests):
    """Independent closed-form membership evaluation, outside the measured service call."""
    table={}
    for key in set(requests):
        hits=tuple((c.uid,c.weight)for c in game.criteria if all(p in key for p in c.required))
        value=game.baseline
        for _,weight in hits:value+=weight
        table[key]=UtilityReceipt(game.uid,key,value,hits)
    rows=tuple(table[key]for key in requests)
    return ReplayReport(game.uid,rows,sum((r.value for r in rows),Fraction(0)))
