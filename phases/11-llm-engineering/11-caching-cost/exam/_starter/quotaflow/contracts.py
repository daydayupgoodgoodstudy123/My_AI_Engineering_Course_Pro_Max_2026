"""Given primitive records and local finite-domain validation."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
US=1_000_000
WINDOW_US=60*US
I64=2**63-1
TIERS={"free":{"capacity":50_000,"refill_rate":500,"max_requests_per_min":10},
       "pro":{"capacity":500_000,"refill_rate":5_000,"max_requests_per_min":60},
       "enterprise":{"capacity":5_000_000,"refill_rate":50_000,"max_requests_per_min":300}}
@dataclass(frozen=True)
class BucketState:
    tokens: int
    last_refill_us: int
    remainder: int=0
    rpm: tuple=()
    total_used: int=0
@dataclass(frozen=True)
class Admission:
    allowed: bool
    retry_after_us: object
    reason: str
    tokens_remaining: int
@dataclass(frozen=True)
class Usage:
    request_id: str
    user: str
    model: str
    admitted: bool
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    cost_text: str
@dataclass(frozen=True)
class Price:
    uncached_input: Decimal
    cached_input: Decimal
    output: Decimal
def integer(value,lower=0):
    if type(value) is not int or not lower<=value<=I64:raise ValueError("integer domain")
def validate_policy(policy):
    for key in ("capacity","refill_rate","max_requests_per_min"):integer(policy[key],1)
def validate_state(state,policy=None):
    for value in (state.tokens,state.last_refill_us,state.total_used):integer(value)
    integer(state.remainder)
    if state.remainder>=US or type(state.rpm) is not tuple:raise ValueError("bucket state")
    previous=-1
    for stamp in state.rpm:
        integer(stamp)
        if not previous<=stamp<=state.last_refill_us:raise ValueError("timestamp order")
        previous=stamp
    if policy is not None and state.tokens>policy["capacity"]:raise ValueError("bucket capacity")
def decimal_cost(text):
    if type(text) is not str:raise ValueError("decimal spelling")
    try:value=Decimal(text)
    except InvalidOperation:raise ValueError("decimal spelling")
    if not value.is_finite() or value<0:raise ValueError("decimal cost")
    return value
def validate_usage(row):
    if any(type(x) is not str or not x for x in (row.request_id,row.user,row.model)):raise ValueError("usage identity")
    if type(row.admitted) is not bool:raise ValueError("admission flag")
    for count in (row.input_tokens,row.cached_input_tokens,row.output_tokens):integer(count)
    if row.cached_input_tokens>row.input_tokens:raise ValueError("cached subset")
    decimal_cost(row.cost_text)
def validate_prices(prices):
    for price in prices.values():
        for value in (price.uncached_input,price.cached_input,price.output):
            if not isinstance(value,Decimal) or not value.is_finite() or value<0:raise ValueError("price")
        if price.cached_input>price.uncached_input:raise ValueError("cached price")

def add_cost(left,right):
    """Given exact finite nonnegative decimal addition for the supplied ledger."""
    with localcontext() as context:
        context.prec=max(left.adjusted(),right.adjusted())-min(left.as_tuple().exponent,right.as_tuple().exponent)+3
        return left+right
