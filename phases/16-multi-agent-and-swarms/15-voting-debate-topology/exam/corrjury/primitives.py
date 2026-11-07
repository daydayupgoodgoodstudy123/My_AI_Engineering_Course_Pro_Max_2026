"""Sample family-shared juries, classify strict majority, and report declared generation/read costs."""
from decimal import Decimal
from fractions import Fraction
from .models import SeatVote,SampleTally,CostBreakdown
from .support import seat_ids,exact_decimal,money_sum
def ticket_outcome(probability,roll):
    """Map a supplied uniform integer roll in [0,denominator) to its exact Bernoulli category."""
    deck=['RIGHT']*probability.numerator+['WRONG']*(probability.denominator-probability.numerator)
    return deck[roll]
def draw_family_trial(config,stream):
    """Draw once per independent family and broadcast that same actual draw/outcome to all its seats."""
    votes=[]
    for family in config.families:
        for seat in seat_ids(family):
            ticket=stream.take(family);outcome=ticket_outcome(family.probability,ticket.roll)
            votes.append(SeatVote(seat,family.uid,ticket.ordinal,outcome))
    return tuple(votes)
def sampled_jury_result(votes):
    """Return actual correct seats, total seats and strict majority for a positive odd-seat sample."""
    correct=sum(v.outcome=='RIGHT'for v in votes);total=len(votes)
    return SampleTally(correct,total,correct>=total//2)
def trial_cost(config):
    """Report separate declared generation/read amounts and their exact total, retaining every read exposure."""
    generation=exact_decimal(sum((f.seats*f.generation_tokens for f in config.families))*Fraction(config.generation_rate))
    reading=Decimal('0')
    return CostBreakdown(generation,reading,money_sum((generation,reading)),config.reads)
