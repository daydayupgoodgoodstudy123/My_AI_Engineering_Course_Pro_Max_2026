from .models import RecoveryReport
from .primitives import CheckpointStore
from .execution_support import CrashCut, bind_plans

def commit_checkpoint_and_intent(archive,plan,crash=None):
    """Commit both durable records together, with no external side effect inside the transaction."""
    crash=crash or CrashCut()
    with archive.atomic():
        archive.write_checkpoint(plan.checkpoint)
        crash.hit('after_checkpoint')
        archive.write_intent(plan.intent)
        crash.hit('before_commit')
    crash.hit('after_commit')

def dispatch_intents(archive,receiver,run,crash=None):
    """Deliver each actual pending stable key before persisting its returned receipt."""
    crash=crash or CrashCut()
    if archive.transaction_open:
        raise ValueError('dispatcher requires committed sender records')
    for intent in archive.pending(run):
        receipt=receiver.deliver(intent)
        crash.hit('after_send')
        with archive.atomic():
            archive.acknowledge(receipt)
    return archive.receipts()

def recover_outbox(archive,receiver,run,plans,crash=None):
    """Drain committed work even at a terminal checkpoint, then continue missing numeric steps."""
    crash=crash or CrashCut()
    plans=bind_plans(run,plans)
    dispatch_intents(archive,receiver,run,crash)
    latest=CheckpointStore(archive.checkpoints()).latest(run)
    for plan in plans:
        if latest is None or plan.checkpoint.step>latest.step:
            commit_checkpoint_and_intent(archive,plan,crash)
            dispatch_intents(archive,receiver,run,crash)
            latest=plan.checkpoint
    return RecoveryReport(CheckpointStore(archive.checkpoints()).latest(run),tuple(i for i in archive.intents() if i.run==run),tuple(r for r in archive.receipts() if r.key[0]==run))
