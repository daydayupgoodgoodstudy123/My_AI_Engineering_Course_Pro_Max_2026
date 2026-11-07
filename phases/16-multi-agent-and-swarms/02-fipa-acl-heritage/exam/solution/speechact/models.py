"""Given local message/state/tree records; no source module is imported."""
from dataclasses import dataclass
ACTS={"inform","request","query-if","query-ref","propose","accept-proposal","reject-proposal","agree","refuse","confirm","disconfirm","not-understood","cfp","subscribe","cancel","failure"}
@dataclass(frozen=True)
class ACLMessage:
    performative:str
    sender:str
    receiver:str
    content:object
    language:str="SL0"
    ontology:str="default"
    protocol:object=None
    conversation_id:object=None
    reply_with:object=None
@dataclass(frozen=True)
class RequestState:
    requester:str
    responder:str
    status:str
@dataclass(frozen=True)
class SubscriptionState:
    subscriber:str
    publisher:str
    active:bool
    notifications:int=0
@dataclass(frozen=True)
class Atom:
    value:str
@dataclass(frozen=True)
class Quoted:
    value:str
@dataclass(frozen=True)
class SList:
    items:tuple
def message_value(message):
    if not isinstance(message,ACLMessage) or message.performative not in ACTS:raise ValueError("unknown performative")
    if any(type(getattr(message,k)) is not str for k in ("sender","receiver","language","ontology")):raise ValueError("envelope string")
    if any(getattr(message,k) is not None and type(getattr(message,k)) is not str for k in ("protocol","conversation_id","reply_with")):raise ValueError("optional envelope string")
    return message
def interaction_key(message):
    message_value(message)
    if message.protocol not in ("fipa-request","fipa-subscribe") or not isinstance(message.conversation_id,str) or not message.conversation_id:raise ValueError("named local interaction required")
    return message.protocol,message.conversation_id
