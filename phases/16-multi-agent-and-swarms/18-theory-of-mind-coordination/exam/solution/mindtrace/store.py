"""Candidate complete observation and belief-version history schemas with independent subject priors."""
from .models import Agent,Observation,BeliefVersion,SubjectPrior,EpistemicSnapshot
from .codec import dump_value,load_value,dump_key,load_key
from .db_support import SnapshotDB
class BeliefArchive:
    def __init__(self,path):self.driver=SnapshotDB(path)
    def save(self,snapshot):
        """Persist all ordered observations and independent believed versions with their own full keys and source links."""
        header=dump_value((snapshot.uid,tuple((a.uid,a.name,a.collected)for a in snapshot.population),tuple((p.subject,p.believed_available,p.preference)for p in snapshot.priors)))
        observations=[(i,o.uid,dump_key(o.key),dump_value(o.value),dump_value(o.turn),dump_value(o.ordinal),o.kind)for i,o in enumerate(snapshot.observations)]
        beliefs=[(i,b.uid,dump_key(b.key),dump_value(b.value),dump_value(b.turn),dump_value(b.ordinal),dump_value(b.source_uid))for i,b in enumerate(snapshot.beliefs)]
        self.driver.replace(header,observations,beliefs)
    def load(self):
        """Reopen the complete independent typed histories, not just a truth column or each key's latest row."""
        header,observations,beliefs=self.driver.read();uid,population,priors=load_value(header)
        obs=tuple(Observation(o[1],load_key(o[2]),load_value(o[3]),load_value(o[4]),load_value(o[5]),o[6])for o in observations)
        versions=tuple(BeliefVersion(b[1],load_key(b[2]),load_value(b[3]),load_value(b[4]),load_value(b[5]),load_value(b[6]))for b in beliefs)
        return EpistemicSnapshot(uid,tuple(Agent(*a)for a in population),obs,versions,tuple(SubjectPrior(*p)for p in priors))
    def close(self):self.driver.close()
