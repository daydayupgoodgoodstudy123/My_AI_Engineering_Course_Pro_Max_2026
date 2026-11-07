"""Immutable scalar/evaluator records; these are not distributed BFT messages."""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
@dataclass(frozen=True,slots=True)
class Proposal:
    uid:str
    agent:str
    kind:str
    answer:str|None
    self_confidence:Fraction
@dataclass(frozen=True,slots=True)
class Probe:
    proposal_uid:str
    probe_uid:str
    confidence:Fraction
    evaluator:str
    assessment:str
@dataclass(frozen=True,slots=True)
class Ballot:
    proposal:Proposal
    probe:Probe
@dataclass(frozen=True,slots=True)
class NumericKey:
    value:Decimal
    unit:str
@dataclass(frozen=True,slots=True)
class ClusterSupport:
    masses:tuple[tuple[NumericKey|None,Fraction],...]
    total:Fraction
    winner:NumericKey|None
    abstentions:tuple[str,...]
@dataclass(frozen=True,slots=True)
class LegacyScore:
    key:NumericKey
    score:Fraction
@dataclass(frozen=True,slots=True)
class Inspection:
    ballots:tuple[Ballot,...]
    canonical:tuple[tuple[str,NumericKey|None],...]
    support:ClusterSupport
    legacy_scores:tuple[LegacyScore,...]
    disagreement:Fraction
    dispersion_alert:bool
@dataclass(frozen=True,slots=True)
class WeightedPosition:
    uid:str
    value:Decimal
    unit:str
    weight:Fraction
@dataclass(frozen=True,slots=True)
class MedianInterval:
    low:Decimal
    high:Decimal
    unit:str
@dataclass(frozen=True,slots=True)
class TruthLabel:
    value:Decimal
    unit:str
@dataclass(frozen=True,slots=True)
class CenterAudit:
    center:Decimal
    unit:str
    support:Fraction
    total:Fraction
    accepted:bool
    minority:tuple[str,...]
    truth:bool|None
@dataclass(frozen=True,slots=True)
class SealedCore:
    core_uid:str
    epoch:int
    proposal_uids:tuple[str,...]
    decision:CenterAudit
@dataclass(frozen=True,slots=True)
class EdgeAck:
    edge_uid:str
    core_uid:str
    epoch:int
    center:Decimal
    unit:str
    references:tuple[str,...]
@dataclass(frozen=True,slots=True)
class CoreGroup:
    core_uid:str
    epoch:int
    claimed_center:Decimal
    unit:str
    edges:tuple[EdgeAck,...]=()
    children:tuple['CoreGroup',...]=()
@dataclass(frozen=True,slots=True)
class EdgeAudit:
    edge_uid:str
    findings:tuple[str,...]
@dataclass(frozen=True,slots=True)
class CoreAudit:
    path:tuple[str,...]
    sealed:SealedCore
    findings:tuple[str,...]
    edges:tuple[EdgeAudit,...]
    children:tuple['CoreAudit',...]
