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
        row=self.db.execute("SELECT tokens,last_us,remainder,rpm,total_used FROM buckets WHERE user=?",(user,)).fetchone()
        if row is None:return None
        return BucketState(row[0],row[1],row[2],tuple(json.loads(row[3])),row[4])
    def save_and_log(self,user,state,usage):
        """Atomically save all bucket fields and append through the given journal.

        State belongs to user, as must usage.user. Use the supplied state
        validation. A rejected journal append must leave the prior saved state
        unchanged. UsageJournal handles every usage field and raw cost spelling
        on self.db; it does not control this operation's transaction boundary.
        Duplicate request ids raise the SQLite integrity error. This local
        transaction does not promise distributed exactly-once processing.
        """
        validate_state(state)
        if usage.user!=user:raise ValueError("usage user")
        with self.db:
            self.db.execute("INSERT INTO buckets VALUES(?,?,?,?,?,?) ON CONFLICT(user) DO UPDATE SET tokens=excluded.tokens,last_us=excluded.last_us,remainder=excluded.remainder,rpm=excluded.rpm,total_used=excluded.total_used",(user,state.tokens,state.last_refill_us,state.remainder,json.dumps(state.rpm),state.total_used))
            self.journal.append(usage)
    def ledger(self):
        """Given wrapper returning the journal's complete insertion-ordered records."""
        return self.journal.read()
