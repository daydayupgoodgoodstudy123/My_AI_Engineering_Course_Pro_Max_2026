"""Complete current-plan binding, finite unique forest intake and single movement state primitive."""
from dataclasses import dataclass,replace
from .models import BoundNode
@dataclass(frozen=True,slots=True)
class World:
    locations:tuple[tuple[str,str],...]
    venues:tuple
    def location(self,agent_uid):return dict(self.locations)[agent_uid]
    def venue(self,uid):return next(v for v in self.venues if v.uid==uid)
    def occupants(self,uid):return tuple(a for a,v in self.locations if v==uid)
    def move(self,agent_uid,destination):
        self.venue(destination);self.location(agent_uid)
        return replace(self,locations=tuple((a,destination if a==agent_uid else v)for a,v in self.locations))
class PlanCatalog:
    def __init__(self,revisions,nodes,venues):
        self.segments={};self.venues={v.uid:v for v in venues};self.nodes={n.uid:n for n in nodes}
        if len(self.nodes)!=len(nodes)or len(self.venues)!=len(venues):raise ValueError('unique tree and venue identities required')
        for result in revisions:
            for s in result.state.plans:
                if s.uid in self.segments:raise ValueError('globally unique segment identities required')
                if s.venue_uid not in self.venues or s.start>=s.end:raise ValueError('bound venue and positive interval required')
                self.segments[s.uid]=(result.state.uid,s)
        if any(v.capacity<0 or any(a>=b for a,b in v.open_intervals)for v in venues):raise ValueError('valid finite venue declarations required')
    def expand(self,roots):
        visited=set()
        def bind(uid,path,parent_agent=None):
            if uid in visited:raise ValueError('finite unique tree required')
            visited.add(uid);n=self.nodes[uid]
            if parent_agent is not None and n.agent_uid!=parent_agent:raise ValueError('one agent per plan tree required')
            if n.segment_uid is not None:
                if n.children:raise ValueError('action leaf required')
                agent,s=self.segments[n.segment_uid]
                if agent!=n.agent_uid:raise ValueError('own current plan segment required')
                return BoundNode(n,path+(uid,),s.start,s.end,s,())
            if n.start>=n.end:raise ValueError('positive branch interval required')
            return BoundNode(n,path+(uid,),n.start,n.end,None,tuple(bind(c,path+(uid,),n.agent_uid)for c in n.children))
        return tuple(bind(uid,())for uid in roots)
