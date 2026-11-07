"""Ordered SQLite audit runs; supplied schema/transaction and value codec are dependencies."""
from .db_support import AuditDatabase
from .value_codec import encode,decode

class AuditRepository:
    def __init__(self,path):self.database=AuditDatabase(path)
    def close(self):self.database.close()

    def save(self,entry):
        """Store the full run and every trajectory slot, replacing that run's prior snapshot."""
        body={key:value for key,value in entry.items() if key!='trajectory'}
        with self.database.transaction() as db:
            db.execute('INSERT INTO runs VALUES(?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET agent=excluded.agent,session_id=excluded.session_id,body=excluded.body',
                (entry['run_id'],entry['agent'],entry['session_id'],encode(body)))
            db.execute('DELETE FROM observations WHERE run_id=?',(entry['run_id'],))
            for slot,step in enumerate(entry['trajectory']):
                db.execute('INSERT INTO observations VALUES(?,?,?)',(entry['run_id'],slot,encode(step)))

    def load(self,run_id):
        """Restore one exact run, ordered by occurrence slot rather than event timestamps."""
        db=self.database.connection
        row=db.execute('SELECT body FROM runs WHERE run_id=?',(run_id,)).fetchone()
        if row is None:raise KeyError(run_id)
        entry=decode(row[0])
        entry['trajectory']=[decode(body) for body, in db.execute('SELECT body FROM observations WHERE run_id=? ORDER BY slot',(run_id,))]
        return entry

    def for_session(self,session_id,agent):
        """Return this exact agent's runs in this exact session in insertion order."""
        rows=self.database.connection.execute('SELECT run_id FROM runs WHERE session_id IS ? AND agent=? ORDER BY rowid',(session_id,agent)).fetchall()
        return [self.load(run_id) for run_id, in rows]
