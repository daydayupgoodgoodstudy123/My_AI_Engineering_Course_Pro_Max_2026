"""Complete role/quote intake, standing-price evidence consumer and policy input binding."""
from .models import PolicyInput
from .exact import amount_atoms,subtract
def validate_strategy(strategy,tick):
    if strategy.side not in('buyer','seller')or not 0<strategy.concession<=1:raise ValueError('declared side and concession required')
    for value in(strategy.reservation,strategy.opening):
        a,b=amount_atoms(value,tick)
        if a%b:raise ValueError('strategy prices must lie on their declared grid')
    if(strategy.side=='buyer'and strategy.opening>strategy.reservation)or(strategy.side=='seller'and strategy.opening<strategy.reservation):raise ValueError('opening must respect own reservation')
    return strategy
def validate_request(request):
    q=request.incoming;amount_atoms(q.price,q.tick)
    if request.buyer.side!='buyer'or request.seller.side!='seller'or q.side not in('buyer','seller'):raise ValueError('bound buyer seller and quote side required')
    if request.standing is not None:
        s=request.standing
        if(s.negotiation_id,s.issue_id,s.tick)!=(q.negotiation_id,q.issue_id,q.tick)or s.side==q.side:raise ValueError('same bargain opposite standing side required')
    return request
def require_quote_price(settlement,standing):
    if standing is None or settlement.standing_uid!=standing.uid or settlement.price!=standing.price:raise ValueError('settlement must retain its referenced standing quote price')
def settlement_receipt(request,settlement):
    if settlement is None:return None,None
    require_quote_price(settlement,request.standing)
    return subtract(request.buyer.reservation,settlement.price),subtract(settlement.price,request.seller.reservation)
def bind_policy(own,prior,counter,tick):
    validate_strategy(own,tick);base=own.opening if prior is None else prior.price
    return PolicyInput(base,counter is not None,base if counter is None else counter.price,own.reservation,tick,own.concession)
