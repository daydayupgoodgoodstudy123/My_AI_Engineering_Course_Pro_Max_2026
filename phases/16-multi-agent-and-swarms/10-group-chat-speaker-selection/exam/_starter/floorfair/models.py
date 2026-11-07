"""Immutable local conversation observations, not a provider protocol."""
from dataclasses import dataclass
from fractions import Fraction
@dataclass(frozen=True,slots=True)
class Speaker:
    name:str
    weight:int=1
    active:bool=True
@dataclass(frozen=True,slots=True)
class Utterance:
    thread:str
    message_id:str
    speaker:str
    content:str
    turn:int
    decision_id:str=''
    question_id:str=''
    addressee:str=''
    reply_to:str=''
    verdict:str=''
@dataclass(frozen=True,slots=True)
class Decision:
    thread:str
    decision_id:str
    speaker:str|None
    reason:str
    context:tuple[str,...]
    turn:int
    accepted:bool
    private_prompt:str=''
@dataclass(frozen=True,slots=True)
class Proposal:
    speaker:str|None
    content:str=''
    accepted:bool=True
    reason:str='scripted'
    question_id:str=''
    addressee:str=''
    reply_to:str=''
    verdict:str=''
    private_prompt:str=''
@dataclass(frozen=True,slots=True)
class ChatReport:
    thread:str
    roster:tuple[Speaker,...]
    history:tuple[Utterance,...]
    records:tuple[Utterance|Decision,...]
    counts:tuple[tuple[str,int],...]
    stop:str
@dataclass(frozen=True,slots=True)
class Snapshot:
    thread:str
    roster:tuple[Speaker,...]
    baseline:tuple[tuple[str,int],...]
    records:tuple[Utterance|Decision,...]
@dataclass(frozen=True,slots=True)
class Question:
    question_id:str
    thread:str
    addressee:str
    message_id:str
@dataclass(frozen=True,slots=True)
class Choice:
    speaker:str
    reason:str
    deficit:Fraction
@dataclass(frozen=True,slots=True)
class TurnObservation:
    thread:str
    turn:int
    kind:str
    speaker:str|None
    reason:str
    deficit_delta:Fraction
    private_prompt:str=''
@dataclass(frozen=True,slots=True)
class Thread:
    name:str
    limit:int
    records:tuple[Utterance|Decision,...]=()
    children:tuple['Thread',...]=()
    max_speaks:tuple[tuple[str,int],...]=()
@dataclass(frozen=True,slots=True)
class SpeakerQuota:
    speaker:str
    limit:int
    used:int
    remaining:int
    first_excess:tuple[str,...]
