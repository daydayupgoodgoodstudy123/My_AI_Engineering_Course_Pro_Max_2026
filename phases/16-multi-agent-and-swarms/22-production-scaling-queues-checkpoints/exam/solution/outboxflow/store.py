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
        self.rows.put('checkpoint',(c.run,c.step),(c.run,c.step,c.version,c.state))
    def checkpoints(self):
        return tuple(Checkpoint(*v) for v in self.rows.all('checkpoint'))
    def write_intent(self,i):
        self.rows.put('intent',i.key,(i.run,i.step,i.effect,i.amount,i.destination,i.payload))
    def intents(self):
        return tuple(Intent(*v) for v in self.rows.all('intent'))
    def acknowledge(self,r):
        self.rows.put('receipt',r.key,(r.key,r.receiver,r.amount,r.result))
    def receipts(self):
        return tuple(Receipt(*v) for v in self.rows.all('receipt'))
    def pending(self,run):
        acknowledged={r.key for r in self.receipts()}
        return tuple(i for i in self.intents() if i.run==run and i.key not in acknowledged)
