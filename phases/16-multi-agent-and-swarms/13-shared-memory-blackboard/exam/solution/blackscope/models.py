"""Immutable domain values; identity resolution and wire capabilities are supplied."""
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class SourceKey:
    uri:str
    version:str
@dataclass(frozen=True,slots=True)
class SourceSnapshot:
    key:SourceKey
    text:str
@dataclass(frozen=True,slots=True)
class Entry:
    entry_id:int
    writer:str
    topic:str
    content:str
    timestamp_ns:int
    prompt_hash:str
    source:SourceKey|None=None
    supersedes:int|None=None
@dataclass(frozen=True,slots=True)
class VerificationFinding:
    entry_id:int
    source:SourceKey
    verdict:str
    detail:str
@dataclass(frozen=True,slots=True)
class PercentReceipt:
    entry_id:int
    claim:str
@dataclass(frozen=True,slots=True)
class SummaryReport:
    entries:tuple[Entry,...]
    receipts:tuple[PercentReceipt,...]
@dataclass(frozen=True,slots=True)
class EvidenceDecision:
    entry:Entry
    status:str
    findings:tuple[VerificationFinding,...]
@dataclass(frozen=True,slots=True)
class ConsumerPolicy:
    role:str
    topics:tuple[str,...]
@dataclass(frozen=True,slots=True)
class Claim:
    claim_id:str
    entry_id:int|None=None
    children:tuple[str,...]=()
    announced_source:str=''
@dataclass(frozen=True,slots=True)
class ExpandedClaim:
    claim:Claim|None
    path:tuple[str,...]
    children:tuple['ExpandedClaim',...]=()
    obstacle:str|None=None
@dataclass(frozen=True,slots=True)
class SupportCertificate:
    path:tuple[str,...]
    required:frozenset[int]
    covered:frozenset[int]
    sources:frozenset[SourceKey]
    obstacles:frozenset[str]
    children:tuple['SupportCertificate',...]=()
    @property
    def complete(self):
        """A complete certificate is coverage, not a declaration of world truth."""
        return bool(self.required) and self.required<=self.covered and bool(self.sources) and not self.obstacles
