"""Clear supplied standing offers and form their complete public numeric narration view."""
from .models import Settlement,Narration,PublicOffer
from .exact import amount_atoms
def try_settlement(incoming,standing,buyer_limit,seller_limit):
    """Clear crossing offers at the opposite standing quote within both inclusive reservation bounds."""
    if standing is None:return None
    crosses=incoming.price>=standing.price if incoming.side=='buyer'else incoming.price<=standing.price
    price=standing.price
    if crosses and seller_limit<=price<=buyer_limit:return Settlement(incoming.negotiation_id,incoming.issue_id,standing.uid,price)
    return None
def count_price_ticks(amount,tick):
    """Return exact nonnegative integral tick count; reject any nonzero off-grid remainder."""
    quotient,remainder=divmod(amount,tick)
    if remainder:raise ValueError('offer is off its declared tick grid')
    return quotient
def public_offer_view(quote,own):
    """Retain the exact numeric quote, its grid count and its approved public narration, without private strategy content."""
    units=count_price_ticks(*amount_atoms(quote.price,quote.tick))
    narration=Narration(quote.uid,quote.revision,f'{quote.side} offers {quote.price} {quote.currency}')
    return PublicOffer(quote,narration,units)
