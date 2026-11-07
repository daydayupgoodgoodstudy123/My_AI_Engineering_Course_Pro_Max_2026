"""Immutable finite toy jury, sampled evidence, exact law and nested model records."""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
@dataclass(frozen=True,slots=True)
class FamilySpec:
    uid:str
    probability:Fraction
    seats:int
    generation_tokens:int
@dataclass(frozen=True,slots=True)
class ReadExposure:
    uid:str
    reader:str
    sender:str
    tokens:int
@dataclass(frozen=True,slots=True)
class JuryConfig:
    uid:str
    families:tuple[FamilySpec,...]
    reads:tuple[ReadExposure,...]
    generation_rate:Decimal
    read_rate:Decimal
@dataclass(frozen=True,slots=True)
class JuryRequest:
    trial_id:str
    config:JuryConfig
@dataclass(frozen=True,slots=True)
class DrawTicket:
    ordinal:int
    family_uid:str
    numerator:int
    denominator:int
    roll:int
@dataclass(frozen=True,slots=True)
class SeatVote:
    seat_uid:str
    family_uid:str
    draw_ordinal:int
    outcome:str
@dataclass(frozen=True,slots=True)
class CostBreakdown:
    generation:Decimal
    reading:Decimal
    total:Decimal
    read_exposures:tuple[ReadExposure,...]
@dataclass(frozen=True,slots=True)
class SampleTally:
    correct_seats:int
    total_seats:int
    passed:bool
@dataclass(frozen=True,slots=True)
class TrialReport:
    trial_id:str
    config:JuryConfig
    draws:tuple[DrawTicket,...]
    votes:tuple[SeatVote,...]
    family_outcomes:tuple[tuple[str,str],...]
    tally:SampleTally
    cost:CostBreakdown
    simulated:bool=True
@dataclass(frozen=True,slots=True)
class BatchReport:
    requests:tuple[JuryRequest,...]
    trials:tuple[TrialReport,...]
    correct_trials:int
    generation:Decimal
    reading:Decimal
    total_cost:Decimal
@dataclass(frozen=True,slots=True)
class FamilyMass:
    family_uid:str
    seats:int
    mass:tuple[Fraction,...]
@dataclass(frozen=True,slots=True)
class ReliabilityReport:
    config_uid:str
    total_seats:int
    threshold:int
    distribution:tuple[Fraction,...]
    probability:Fraction
    cost:CostBreakdown
@dataclass(frozen=True,slots=True)
class FamilyProfile:
    uid:str
    probability:Fraction
    generation_tokens:int
@dataclass(frozen=True,slots=True)
class JuryNode:
    uid:str
    allocations:tuple[tuple[str,int],...]
    reads:tuple[ReadExposure,...]=()
    children:tuple[str,...]=()
@dataclass(frozen=True,slots=True)
class JuryOccurrence:
    node:JuryNode
    path:tuple[str,...]
    children:tuple['JuryOccurrence',...]
@dataclass(frozen=True,slots=True)
class JuryAudit:
    path:tuple[str,...]
    family_counts:tuple[tuple[str,int],...]
    config:JuryConfig
    exact:ReliabilityReport
    children:tuple['JuryAudit',...]
