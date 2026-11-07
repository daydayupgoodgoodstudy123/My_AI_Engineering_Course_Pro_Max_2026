"""Own-only directional concession, feasible tick progress/reservation clamp and bounded alternating mechanism."""
from dataclasses import replace
from fractions import Fraction
from .exact import tick_price
from .models import BargainResult
from .mechanism_support import buyer_input,seller_input,units,make_quote,supplied_request
from .service import OfferDesk
def next_buyer_offer(data):
    """Move from own prior toward standing ask, at least one feasible tick, never beyond own reservation."""
    if not data.has_counter or data.counter<=data.base:return data.base
    base=units(data.base,data.tick);limit=units(data.reservation,data.tick)
    gap=Fraction(data.counter)-Fraction(data.base)
    steps=max(1,(gap*Fraction(data.concession))//Fraction(data.tick))
    return tick_price(min(limit,base+steps),data.tick)
def next_seller_offer(data):
    """Move from own prior toward standing bid, at least one feasible tick, never below own reservation."""
    if not data.has_counter or data.counter>=data.base:return data.base
    base=units(data.base,data.tick);limit=units(data.reservation,data.tick)
    gap=Fraction(data.base)-Fraction(data.counter)
    steps=max(1,(gap*Fraction(data.concession))//Fraction(data.tick))
    return tick_price(max(limit,base-steps),data.tick)
def run_bargain(saved,max_rounds):
    """Resume the declared alternating phase up to a total full-round ceiling, stopping at deal/no-ZOPA/exhaustion."""
    if saved.state.closed is not None:return BargainResult(saved,(),saved.state.closed)
    if saved.buyer.reservation<saved.seller.reservation:
        return BargainResult(replace(saved,state=replace(saved.state,closed='no-zopa')),(),'no-zopa')
    current=saved;produced=[];desk=OfferDesk()
    while current.state.round<max_rounds:
        s=current.state;side=s.next_side
        price=next_buyer_offer(buyer_input(current))if side=='buyer'else next_seller_offer(seller_input(current))
        quote=make_quote(s,side,price);receipt=desk.evaluate_supplied(supplied_request(current,quote));produced.append(receipt.public)
        changes={'revision':quote.revision,'buyer_quote'if side=='buyer'else'seller_quote':quote,'next_side':'seller'if side=='buyer'else'buyer','round':s.round+(side=='seller')}
        if receipt.settlement is not None:changes.update(closed='deal',settlement=receipt.settlement)
        current=replace(current,state=replace(s,**changes),offers=current.offers+(receipt.public,))
        if receipt.settlement is not None:return BargainResult(current,tuple(produced),'deal')
    current=replace(current,state=replace(current.state,closed='exhausted'))
    return BargainResult(current,tuple(produced),'exhausted')
