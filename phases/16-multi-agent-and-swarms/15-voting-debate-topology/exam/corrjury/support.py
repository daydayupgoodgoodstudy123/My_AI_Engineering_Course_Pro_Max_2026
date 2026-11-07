"""Complete exact money, legal config/catalog, replay tickets and shared-draw evidence consumers."""
from decimal import Decimal
from fractions import Fraction
import random
from .models import DrawTicket
def exact_decimal(value):
    value=Fraction(value);sign=int(value<0);n=abs(value.numerator);d=value.denominator;twos=fives=0
    while d%2==0:twos+=1;d//=2
    while d%5==0:fives+=1;d//=5
    if d!=1:raise ValueError('finite decimal amount required')
    scale=max(twos,fives);n*=2**(scale-twos)*5**(scale-fives)
    return Decimal((sign,tuple(map(int,str(n))),-scale))
def money_sum(values):return exact_decimal(sum((Fraction(value)for value in values),Fraction()))
def seat_ids(family):return tuple(family.uid+'#'+str(i)for i in range(family.seats))
def validate_config(config):
    ids=[f.uid for f in config.families];total=sum(f.seats for f in config.families)
    if len(set(ids))!=len(ids)or not total or total%2==0:raise ValueError('unique independent families and positive odd seats required')
    if any(type(f.seats)is not int or f.seats<=0 or type(f.probability)is not Fraction or not 0<=f.probability<=1 or f.generation_tokens<0 for f in config.families):raise ValueError('positive family seats and exact declared probabilities required')
    if not config.generation_rate.is_finite()or not config.read_rate.is_finite()or min(config.generation_rate,config.read_rate)<0 or any(e.tokens<0 for e in config.reads):raise ValueError('finite nonnegative declared costs required')
    return config
class ReplayTicketStream:
    """Record each actual local uniform integer draw, in order, without invoking a model."""
    def __init__(self,seed):self._rng=random.Random(seed);self._draws=[]
    @property
    def cursor(self):return len(self._draws)
    def take(self,family):
        p=family.probability;draw=DrawTicket(len(self._draws),family.uid,p.numerator,p.denominator,self._rng.randrange(p.denominator));self._draws.append(draw);return draw
    def since(self,cursor):return tuple(self._draws[cursor:])
def require_shared_family_draw(config,votes,draws):
    expected=tuple((seat,f.uid)for f in config.families for seat in seat_ids(f));actual=tuple((vote.seat_uid,vote.family_uid)for vote in votes)
    if actual!=expected:raise ValueError('sample must cover declared seats in order')
    by_ordinal={d.ordinal:d for d in draws}
    if len(draws)!=len(config.families):raise ValueError('each family must use one shared draw')
    for family in config.families:
        members=tuple(v for v in votes if v.family_uid==family.uid);ordinals={v.draw_ordinal for v in members}
        if len(ordinals)!=1 or len({v.outcome for v in members})!=1:raise ValueError('each family must use one shared draw')
        ticket=by_ordinal[next(iter(ordinals))]
        if ticket.family_uid!=family.uid or (ticket.numerator,ticket.denominator)!=(family.probability.numerator,family.probability.denominator):raise ValueError('sample ticket must retain its own family probability')
def seal_sample(config,votes,draws):
    """Validate general sample-provenance invariants before downstream statistics consume votes."""
    require_shared_family_draw(config,votes,draws)
    return tuple(votes),tuple(draws)
def canonical_family_outcomes(config,votes):
    return tuple((family.uid,next(v.outcome for v in votes if v.family_uid==family.uid))for family in config.families)
