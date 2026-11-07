from dataclasses import dataclass,field
@dataclass(frozen=True)
class FrozenAgent:
    name:str
    answer:float
    confidence:float
@dataclass
class Agent:
    name:str
    answer:float
    confidence:float
    history:list[float]=field(default_factory=list)
@dataclass(frozen=True)
class RoundRecord:
    index:int
    agents:tuple[FrozenAgent,...]
    truth:float|None
@dataclass(frozen=True)
class DebateArchive:
    names:tuple[str,...]
    records:tuple[RoundRecord,...]
