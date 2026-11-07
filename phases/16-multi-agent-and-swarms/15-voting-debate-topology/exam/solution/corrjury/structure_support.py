"""Complete family/node identity, finite ordered expansion and flat-config construction, not cause aggregation."""
from .models import JuryConfig,FamilySpec,JuryOccurrence
from .support import validate_config
class JuryCatalog:
    def __init__(self,profiles,nodes,generation_rate,read_rate):
        self._families={f.uid:f for f in profiles};self._nodes={n.uid:n for n in nodes};self.generation_rate=generation_rate;self.read_rate=read_rate
        if len(self._families)!=len(profiles)or len(self._nodes)!=len(nodes):raise ValueError('globally unique families and nodes required')
    def expand(self,root):
        seen=set()
        def visit(uid,path):
            if uid in seen:raise ValueError('finite unique node tree required')
            seen.add(uid);node=self._nodes[uid]
            if any(f not in self._families or type(count)is not int or count<=0 for f,count in node.allocations):raise ValueError('declared positive family allocations required')
            here=path+(uid,);return JuryOccurrence(node,here,tuple(visit(child,here)for child in node.children))
        return visit(root,())
    def config(self,uid,counts,reads):
        families=tuple(FamilySpec(family,self._families[family].probability,count,self._families[family].generation_tokens)for family,count in counts)
        return validate_config(JuryConfig(uid,families,tuple(reads),self.generation_rate,self.read_rate))
