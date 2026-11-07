"""Existing supplied-credit statement, synthetic auction, confirmed EMA and utility-oracle contracts."""
from fractions import Fraction
from .models import Efficiency,Payment
from .game_support import coalition_key,validate_game

def efficiency_report(game,allocations,empty,grand):
    """Report exact allocated credit against grand-minus-empty coalition surplus; no allocator is provided."""
    allocated=sum((value for _,value in allocations),Fraction(0))
    surplus=grand-empty
    return Efficiency(game.uid,empty,grand,allocated,surplus,surplus-allocated)

def second_price_payment(bids):
    """Return the first highest bidder with the second-highest charge; fewer than two bids has no sale."""
    if len(bids)<2:return None
    ranked=sorted(bids,key=lambda x:x.amount,reverse=True)
    return Payment(ranked[0].agent,ranked[1].amount)

def update_reputation(current,receipt,alpha=Fraction(1,2),floor=Fraction(1,10)):
    """Only an independently confirmed quality observation updates per-use EMA; unconfirmed receipts leave it unchanged."""
    if not receipt.confirmed:return current
    return max(floor,alpha*current+(1-alpha)*receipt.quality)

class CoalitionOracle:
    """Own one immutable game's exact utility observations, without producing any player allocation."""
    def __init__(self,game,evaluator):
        self.game=validate_game(game)
        if evaluator.game!=game:raise ValueError('evaluator must bind this immutable game')
        self.evaluator=evaluator;self._cache={}
    def value(self,members):
        """Return this game's exact observation for the declared coalition set."""
        key=coalition_key(self.game,members)
        if key not in self._cache:self._cache[key]=self.evaluator.evaluate(key)
        return self._cache[key]
