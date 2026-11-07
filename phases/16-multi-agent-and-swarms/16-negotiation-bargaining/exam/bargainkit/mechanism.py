"""Own-only directional concession, feasible tick progress/reservation clamp and bounded alternating mechanism."""
from dataclasses import replace
from fractions import Fraction
from .exact import tick_price
from .models import BargainResult
from .mechanism_support import buyer_input,seller_input,units,make_quote,supplied_request
from .service import OfferDesk
def next_buyer_offer(data):
    """Move from own prior toward standing ask, at least one feasible tick, never beyond own reservation."""
    raise NotImplementedError
def next_seller_offer(data):
    """Move from own prior toward standing bid, at least one feasible tick, never below own reservation."""
    raise NotImplementedError
def run_bargain(saved,max_rounds):
    """Resume the declared alternating phase up to a total full-round ceiling, stopping at deal/no-ZOPA/exhaustion."""
    raise NotImplementedError
