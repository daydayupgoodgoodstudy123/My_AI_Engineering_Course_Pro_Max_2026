from .db_support import Rows
from .models import Checkpoint, Intent, Receipt

class DurableArchive:
    """Domain records participate in caller-owned atomic scope; writes never commit independently."""
    def __init__(self,path):
        self.rows=Rows(path)
    @property
    def transaction_open(self):
        return self.rows.conn.in_transaction
    def atomic(self):
        return self.rows.atomic()
    def close(self):
        self.rows.close()
    def write_checkpoint(self,c):
        raise NotImplementedError('Complete the declared domain contract')
    def checkpoints(self):
        raise NotImplementedError('Complete the declared domain contract')
    def write_intent(self,i):
        raise NotImplementedError('Complete the declared domain contract')
    def intents(self):
        raise NotImplementedError('Complete the declared domain contract')
    def acknowledge(self,r):
        raise NotImplementedError('Complete the declared domain contract')
    def receipts(self):
        raise NotImplementedError('Complete the declared domain contract')
    def pending(self,run):
        raise NotImplementedError('Complete the declared domain contract')
