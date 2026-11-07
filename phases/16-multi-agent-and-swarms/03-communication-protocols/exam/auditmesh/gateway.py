"""Local trust-gated gateway over corrected capture and persisted observations."""
from copy import deepcopy
from .capture import capture_once
from .models import validate_parts

def validate_declared_output(parts,modes):
    """Accept all and only parts whose tagged MIME modality is declared by the card."""
    raise NotImplementedError

def public_step(step,policy):
    """Project one observed step without exporting private reasoning or arbitrary fields."""
    raise NotImplementedError

def project_task_and_public_audit(entry,policy,accepted=True):
    """Derive a task and policy-redacted audit from one persisted run, with no execution."""
    raise NotImplementedError

class ProtocolGateway:
    def __init__(self,cards,trust,store,repository,clock,next_id,policy):
        self.cards=cards;self.trust=trust;self.store=store;self.repository=repository
        self.clock=clock;self.next_id=next_id;self.policy=policy

    def delegate(self,caller,agent,inputs,handler,session_id=None):
        """Admit before effects, capture once, persist, validate modes, then project that run."""
        raise NotImplementedError
