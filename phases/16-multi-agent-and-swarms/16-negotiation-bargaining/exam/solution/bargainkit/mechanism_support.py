"""Complete own-information policy binding and quote factory; no concession or bounded-run solver."""
from .models import Quote,SuppliedRequest
from .support import bind_policy
from .exact import amount_atoms,tick_price
from . import primitives
def buyer_input(saved):return bind_policy(saved.buyer,saved.state.buyer_quote,saved.state.seller_quote,saved.state.tick)
def seller_input(saved):return bind_policy(saved.seller,saved.state.seller_quote,saved.state.buyer_quote,saved.state.tick)
def units(price,tick):return primitives.count_price_ticks(*amount_atoms(price,tick))
def make_quote(state,side,price):return Quote(state.negotiation_id+'/q'+str(state.revision+1),state.negotiation_id,state.issue_id,state.revision+1,state.round,side,price,state.tick)
def supplied_request(saved,quote):return SuppliedRequest(quote,saved.state.seller_quote if quote.side=='buyer'else saved.state.buyer_quote,saved.buyer,saved.seller)
