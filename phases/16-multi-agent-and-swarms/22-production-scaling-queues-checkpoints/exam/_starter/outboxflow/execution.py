from .models import RecoveryReport
from .primitives import CheckpointStore
from .execution_support import CrashCut, bind_plans

def commit_checkpoint_and_intent(archive,plan,crash=None):
    """Commit both durable records together, with no external side effect inside the transaction."""
    raise NotImplementedError('Complete the declared domain contract')

def dispatch_intents(archive,receiver,run,crash=None):
    """Deliver each actual pending stable key before persisting its returned receipt."""
    raise NotImplementedError('Complete the declared domain contract')

def recover_outbox(archive,receiver,run,plans,crash=None):
    """Drain committed work even at a terminal checkpoint, then continue missing numeric steps."""
    raise NotImplementedError('Complete the declared domain contract')
