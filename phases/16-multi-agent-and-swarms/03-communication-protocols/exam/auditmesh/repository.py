"""Ordered SQLite audit runs; supplied schema/transaction and value codec are dependencies."""
from .db_support import AuditDatabase
from .value_codec import encode,decode

class AuditRepository:
    def __init__(self,path):self.database=AuditDatabase(path)
    def close(self):self.database.close()

    def save(self,entry):
        """Store the full run and every trajectory slot, replacing that run's prior snapshot."""
        raise NotImplementedError

    def load(self,run_id):
        """Restore one exact run, ordered by occurrence slot rather than event timestamps."""
        raise NotImplementedError

    def for_session(self,session_id,agent):
        """Return this exact agent's runs in this exact session in insertion order."""
        raise NotImplementedError
