from .models import BurstReport
from .primitives import CheckpointStore, BurstMailbox

def read_required_state(checkpoint, field):
    return checkpoint.state[field]

def resume_checkpoint(index, run, field):
    return read_required_state(index.latest(run), field)

class QueueDesk:
    """Explicit batch input adapter; not a claim of concurrent three-state processing."""
    def drain_burst(self, messages):
        delivered = BurstMailbox(messages).drain()
        counts = {}
        amount = 0
        for message in delivered:
            counts[message.run] = counts.get(message.run, 0) + 1
            amount += message.amount
        return BurstReport(delivered, tuple(counts.items()), amount)
