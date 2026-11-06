"""SQLite bucket snapshots sharing a transaction with the supplied usage journal."""
import sqlite3,json
from .contracts import BucketState,validate_state
from .journal import UsageJournal
class LedgerStore:
    def __init__(self,path):
        """Given connection, bucket schema and complete UsageJournal wiring."""
        self.db=sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS buckets(user TEXT PRIMARY KEY,tokens INTEGER NOT NULL,last_us INTEGER NOT NULL,remainder INTEGER NOT NULL,rpm TEXT NOT NULL,total_used INTEGER NOT NULL)")
        self.journal=UsageJournal(self.db)
    def close(self):self.db.close()
    def load(self,user):
        """Return the entire saved state, or None; reopening grants no new balance."""
        raise NotImplementedError
    def save_and_log(self,user,state,usage):
        """Atomically save all bucket fields and append through the given journal.

        State belongs to user, as must usage.user. Use the supplied state
        validation. A rejected journal append must leave the prior saved state
        unchanged. UsageJournal handles every usage field and raw cost spelling
        on self.db; it does not control this operation's transaction boundary.
        Duplicate request ids raise the SQLite integrity error. This local
        transaction does not promise distributed exactly-once processing.
        """
        raise NotImplementedError
    def ledger(self):
        """Given wrapper returning the journal's complete insertion-ordered records."""
        return self.journal.read()
