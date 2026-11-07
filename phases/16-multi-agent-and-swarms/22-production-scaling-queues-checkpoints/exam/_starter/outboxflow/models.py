from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class Checkpoint:
    run: str
    step: int
    version: str
    state: dict

@dataclass(frozen=True, slots=True)
class Envelope:
    uid: str
    run: str
    amount: int
    body: str

@dataclass(frozen=True, slots=True)
class BurstReport:
    delivered: tuple
    run_counts: tuple
    amount: int

@dataclass(frozen=True, slots=True)
class Intent:
    run: str
    step: int
    effect: str
    amount: Decimal
    destination: str
    payload: dict
    @property
    def key(self):
        return (self.run, self.step, self.effect)

@dataclass(frozen=True, slots=True)
class Receipt:
    key: tuple
    receiver: str
    amount: Decimal
    result: dict

@dataclass(frozen=True, slots=True)
class StepPlan:
    checkpoint: Checkpoint
    intent: Intent

@dataclass(frozen=True, slots=True)
class RecoveryReport:
    checkpoint: object
    intents: tuple
    receipts: tuple

@dataclass(frozen=True, slots=True)
class DeployEvent:
    kind: str
    run: str
    version: str

@dataclass(frozen=True, slots=True)
class Message:
    uid: str
    run: str
    source: str
    destination: str
    hops: tuple
    kind: str
    payload: dict

@dataclass(frozen=True, slots=True)
class Group:
    uid: str
    admin: str
    agents: tuple
    children: tuple = ()
    messages: tuple = ()
    exports: tuple = ()

@dataclass(frozen=True, slots=True)
class BoundMessage:
    message: Message
    source_path: tuple
    destination_path: tuple
    origin_valid: bool

@dataclass(frozen=True, slots=True)
class RouteAudit:
    uid: str
    run: str
    expected_hops: tuple
    accepted: bool
    reasons: tuple

@dataclass(frozen=True, slots=True)
class GroupAudit:
    uid: str
    path: tuple
    own: tuple
    children: tuple
    outputs: tuple
