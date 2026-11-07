"""Immutable finite game, accounting, sampling and nested-team records."""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
@dataclass(frozen=True,slots=True)
class Criterion:
    uid:str
    required:frozenset[str]
    weight:Fraction
@dataclass(frozen=True,slots=True)
class Game:
    uid:str
    players:tuple[str,...]
    baseline:Fraction
    criteria:tuple[Criterion,...]
@dataclass(frozen=True,slots=True)
class UtilityReceipt:
    game_uid:str
    coalition:frozenset[str]
    value:Fraction
    contributions:tuple[tuple[str,Fraction],...]
@dataclass(frozen=True,slots=True)
class Efficiency:
    game_uid:str
    empty:Fraction
    grand:Fraction
    allocated:Fraction
    surplus:Fraction
    residual:Fraction
@dataclass(frozen=True,slots=True)
class Bid:
    agent:str
    amount:Fraction
@dataclass(frozen=True,slots=True)
class Payment:
    winner:str
    charge:Fraction
@dataclass(frozen=True,slots=True)
class QualityReceipt:
    uid:str
    agent:str
    reported:Fraction
    confirmed:bool
    quality:Fraction
@dataclass(frozen=True,slots=True)
class ReplayReport:
    game_uid:str
    observations:tuple[UtilityReceipt,...]
    total:Fraction
@dataclass(frozen=True,slots=True)
class Marginal:
    player:str
    before:frozenset[str]
    before_value:Fraction
    after_value:Fraction
    weight:Fraction
@dataclass(frozen=True,slots=True)
class AllocationBlock:
    game_uid:str
    mode:str
    players:tuple[str,...]
    totals:tuple[Fraction,...]
    requested:int=0
    completed:int=0
    permutations:tuple[tuple[str,...],...]=()
    marginals:tuple[Marginal,...]=()
@dataclass(frozen=True,slots=True)
class AllocationReport:
    game_uid:str
    players:tuple[str,...]
    credits:tuple[Fraction,...]
    mode:str
    requested:int
    completed:int
    partial:bool
    approximate:bool
    efficiency:Efficiency
@dataclass(frozen=True,slots=True)
class AccountingSnapshot:
    game:Game
    replay:ReplayReport
    permutations:tuple[tuple[str,...],...]
    receipts:tuple[QualityReceipt,...]
    allocations:tuple[tuple[str,Fraction],...]
    statement:Efficiency
    unit:str='synthetic-credit'
    quantum:Decimal=Decimal('0.0100')
@dataclass(frozen=True,slots=True)
class Primitive:
    uid:str
@dataclass(frozen=True,slots=True)
class Team:
    uid:str
    children:tuple[object,...]
@dataclass(frozen=True,slots=True)
class TeamSupport:
    child_uid:str
    before_children:frozenset[str]
    before_members:frozenset[str]
    introduced_members:frozenset[str]
    after_members:frozenset[str]
    marginal:Fraction
    weight:Fraction
@dataclass(frozen=True,slots=True)
class TeamAudit:
    uid:str
    members:frozenset[str]
    players:tuple[str,...]
    credits:tuple[Fraction,...]
    efficiency:Efficiency
    support:tuple[TeamSupport,...]
    children:tuple['TeamAudit',...]
