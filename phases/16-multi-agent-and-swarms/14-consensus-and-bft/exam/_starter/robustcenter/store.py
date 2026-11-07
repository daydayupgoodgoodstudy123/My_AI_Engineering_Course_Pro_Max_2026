"""Model complete proposal and actual independent probe snapshots, preserving original field provenance."""
from .models import Proposal,Probe,Ballot
from .database_support import Database,encode_fraction,decode_fraction
class ProposalArchive:
    def __init__(self,path):self._database=Database(path)
    def save(self,run,ballots):
        """Persist every proposal and its actual independent probe, never substitute self-confidence."""
        raise NotImplementedError
    def load(self,run):
        """Reopen all ordered proposals and complete original evaluator evidence without inventing another probe."""
        raise NotImplementedError
    def close(self):self._database.close()
