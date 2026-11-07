"""Candidate complete observation and belief-version history schemas with independent subject priors."""
from .models import Agent,Observation,BeliefVersion,SubjectPrior,EpistemicSnapshot
from .codec import dump_value,load_value,dump_key,load_key
from .db_support import SnapshotDB
class BeliefArchive:
    def __init__(self,path):self.driver=SnapshotDB(path)
    def save(self,snapshot):
        """Persist all ordered observations and independent believed versions with their own full keys and source links."""
        raise NotImplementedError
    def load(self):
        """Reopen the complete independent typed histories, not just a truth column or each key's latest row."""
        raise NotImplementedError
    def close(self):self.driver.close()
