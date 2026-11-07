"""Domain-owned complete per-agent memory/progress/belief/plan snapshot association."""
from .models import Memory,Progress,Belief,Segment,AgentState,TownSnapshot
from .directory_support import DirectoryDriver
class TownArchive:
    def __init__(self,path):self.driver=DirectoryDriver(path)
    def save(self,snapshot):
        """Save the declared agent order and each independent complete state, including progress when beliefs are empty."""
        documents=[]
        for a in snapshot.agents:
            document={'uid':a.uid,'name':a.name,'location':a.location,'memories':tuple((m.uid,m.seq,m.tick,m.kind,m.content,m.importance,m.source_ids,m.contradicts)for m in a.memories),'progress':(a.progress.consumed_source_ids,a.progress.last_reflection_tick),'beliefs':tuple((b.uid,b.text,b.source_ids)for b in a.beliefs),'plans':tuple((s.uid,s.revision,s.start,s.end,s.venue_uid,s.note,s.status,s.cause_ids)for s in a.plans)}
            documents.append((a.uid,document))
        manifest={'uid':snapshot.uid,'now':snapshot.now,'wall_origin':snapshot.wall_origin,'agents':tuple(a.uid for a in snapshot.agents)}
        self.driver.write(manifest,documents)
    def load(self):
        """Reopen all declared states in manifest order using their own memory, progress and plan records."""
        manifest,documents=self.driver.read();agents=[]
        for uid in manifest['agents']:
            d=documents[uid]
            agents.append(AgentState(d['uid'],d['name'],d['location'],tuple(Memory(*m)for m in d['memories']),Progress(*d['progress']),tuple(Belief(*b)for b in d['beliefs']),tuple(Segment(*s)for s in d['plans'])))
        return TownSnapshot(manifest['uid'],manifest['now'],manifest['wall_origin'],tuple(agents))
    def close(self):self.driver.close()
