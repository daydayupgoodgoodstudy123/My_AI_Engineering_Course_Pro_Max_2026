"""Immutable private strategy, numeric quote, public observation and nested feasibility records."""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
@dataclass(frozen=True,slots=True)
class Strategy:
    party:str
    side:str
    reservation:Decimal
    opening:Decimal
    concession:Fraction|Decimal
@dataclass(frozen=True,slots=True)
class Quote:
    uid:str
    negotiation_id:str
    issue_id:str
    revision:int
    round:int
    side:str
    price:Decimal
    tick:Decimal
    currency:str='USD'
@dataclass(frozen=True,slots=True)
class Narration:
    quote_uid:str
    revision:int
    text:str
@dataclass(frozen=True,slots=True)
class PublicOffer:
    quote:Quote
    narration:Narration
    price_ticks:int
@dataclass(frozen=True,slots=True)
class Settlement:
    negotiation_id:str
    issue_id:str
    standing_uid:str
    price:Decimal
@dataclass(frozen=True,slots=True)
class SuppliedRequest:
    incoming:Quote
    standing:Quote|None
    buyer:Strategy
    seller:Strategy
@dataclass(frozen=True,slots=True)
class ReviewReceipt:
    request:SuppliedRequest
    settlement:Settlement|None
    buyer_surplus:Decimal|None
    seller_surplus:Decimal|None
    settlement_ticks:int|None
    public:PublicOffer
@dataclass(frozen=True,slots=True)
class BatchReview:
    requests:tuple[SuppliedRequest,...]
    receipts:tuple[ReviewReceipt,...]
    settled:int
@dataclass(frozen=True,slots=True)
class BargainState:
    negotiation_id:str
    issue_id:str
    tick:Decimal
    round:int=0
    revision:int=0
    next_side:str='buyer'
    buyer_quote:Quote|None=None
    seller_quote:Quote|None=None
    closed:str|None=None
    settlement:Settlement|None=None
@dataclass(frozen=True,slots=True)
class SavedBargain:
    checkpoint_uid:str
    state:BargainState
    buyer:Strategy
    seller:Strategy
    offers:tuple[PublicOffer,...]=()
@dataclass(frozen=True,slots=True)
class BargainResult:
    saved:SavedBargain
    new_offers:tuple[PublicOffer,...]
    status:str
@dataclass(frozen=True,slots=True)
class PolicyInput:
    base:Decimal
    has_counter:bool
    counter:Decimal
    reservation:Decimal
    tick:Decimal
    concession:Fraction|Decimal
@dataclass(frozen=True,slots=True)
class PublicEvent:
    negotiation_id:str
    round:int
    side:str
    kind:str
    quote:Quote|None
    narration_revision:int|None
@dataclass(frozen=True,slots=True)
class UtilityRule:
    issue_id:str
    unit_value:Decimal
    cash_weight:Decimal
@dataclass(frozen=True,slots=True)
class PartyUtility:
    uid:str
    rules:tuple[UtilityRule,...]
@dataclass(frozen=True,slots=True)
class OfferTerm:
    uid:str
    issue_id:str
    quantity:Decimal
    price:Decimal
    minimum_quantity:Decimal
    maximum_quantity:Decimal
@dataclass(frozen=True,slots=True)
class OfferGroup:
    uid:str
    required_issues:tuple[str,...]
    minimum_utilities:tuple[tuple[str,Decimal],...]
    terms:tuple[OfferTerm,...]=()
    children:tuple[str,...]=()
@dataclass(frozen=True,slots=True)
class OfferOccurrence:
    group:OfferGroup
    path:tuple[str,...]
    children:tuple['OfferOccurrence',...]
@dataclass(frozen=True,slots=True)
class Blocker:
    path:tuple[str,...]
    term_uid:str|None
    category:str
    party_uid:str|None=None
@dataclass(frozen=True,slots=True)
class PrivateGroupAudit:
    path:tuple[str,...]
    terms:tuple[OfferTerm,...]
    utilities:tuple[tuple[str,Decimal],...]
    feasible:bool
    first_blocker:Blocker|None
    children:tuple['PrivateGroupAudit',...]
    minimum_utilities:tuple[tuple[str,Decimal],...]=()
