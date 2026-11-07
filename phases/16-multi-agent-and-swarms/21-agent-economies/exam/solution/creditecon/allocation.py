"""Exact subset marginals, fresh complete permutations and completed-block allocation reports."""
from fractions import Fraction
from itertools import combinations
from math import factorial
from .models import Marginal,AllocationBlock,AllocationReport
from .allocation_support import bind_oracle,validate_blocks
from .primitives import efficiency_report

def shapley_exact(game,oracle):
    """Compute each player's exact weighted subset marginals, retaining every signed evidence term."""
    players=bind_oracle(game,oracle);n=len(players);credits=[];evidence=[]
    for p in players:
        others=tuple(x for x in players if x!=p);credit=Fraction(0)
        for size in range(n):
            weight=Fraction(factorial(size)*factorial(n-size-1),factorial(n))
            for subset in combinations(others,size):
                before=frozenset(subset);low=oracle.value(before).value;high=oracle.value(before|{p}).value
                credit+=weight*(high-low);evidence.append(Marginal(p,before,low,high,weight))
        credits.append(credit)
    return AllocationBlock(game.uid,'exact',players,tuple(credits),marginals=tuple(evidence))

def shapley_sampled(game,oracle,samples,rng):
    """Sample fresh complete seeded permutations; store marginal totals and actual completed traces."""
    players=bind_oracle(game,oracle)
    if type(samples)is not int or samples<0:raise ValueError('nonnegative integer sample request required')
    totals={p:Fraction(0)for p in players};orders=[]
    for _ in range(samples):
        order=list(players);rng.shuffle(order);orders.append(tuple(order));before=frozenset();low=oracle.value(before).value
        for p in order:
            after=before|{p};high=oracle.value(after).value;totals[p]+=high-low;before=after;low=high
    return AllocationBlock(game.uid,'sampled',players,tuple(totals[p]for p in players),samples,len(orders),tuple(orders))

def allocation_report(game,oracle,blocks):
    """Combine actual completed sample totals, label approximation/partial work, and use the supplied efficiency helper."""
    bind_oracle(game,oracle);mode=validate_blocks(game,blocks)
    requested=sum(b.requested for b in blocks);completed=sum(b.completed for b in blocks)
    if mode=='exact':credits=blocks[0].totals
    else:credits=tuple(sum((b.totals[i]for b in blocks),Fraction(0))/completed if completed else Fraction(0)for i in range(len(game.players)))
    efficiency=efficiency_report(game,tuple(zip(game.players,credits)),oracle.value(()).value,oracle.value(game.players).value)
    return AllocationReport(game.uid,game.players,credits,mode,requested,completed,mode=='sampled'and completed<requested,mode=='sampled',efficiency)
