"""Complete finite-input binding, logical clock, provider and corrected breaker resources. No cascade solver. Given."""
from .breaker_given import CircuitBreaker
from .models import CallNode
class LogicalClock:
    def __init__(self,start=0):self.now=start
    def tick(self):
        value=self.now;self.now+=1;return value
class ScriptedProvider:
    def __init__(self,outcomes):
        self.outcomes={k:tuple(v)for k,v in outcomes.items()};self.counts={};self.calls=[]
        if any(not v or any(type(x)is not bool for x in v)for v in self.outcomes.values()):raise ValueError('nonempty actual bool outcomes required')
    def invoke(self,node):
        index=self.counts.get(node.uid,0);values=self.outcomes[node.uid];success=values[min(index,len(values)-1)]
        self.counts[node.uid]=index+1;self.calls.append((node.uid,node.service,success));return success
class CascadeIntake:
    def __init__(self,record,nodes,provider,breakers=None,clock=None):
        self.record=record;self.nodes=tuple(nodes);self.provider=provider;self.clock=clock or LogicalClock();self.effects={};self.used=0
        if type(record.call_budget)is not int or record.call_budget<0:raise ValueError('nonnegative root call budget required')
        self.catalog={}
        def bind(node):
            if not isinstance(node,CallNode)or not node.uid or not node.service or node.uid in self.catalog or type(node.attempts)is not int or node.attempts<=0:raise ValueError('finite unique effect nodes required')
            self.catalog[node.uid]=node
            for child in node.children:bind(child)
        for node in self.nodes:bind(node)
        if set(self.catalog)-set(provider.outcomes):raise ValueError('provider fixture for every effect required')
        self.breakers=breakers if breakers is not None else {node.service:CircuitBreaker(100,1,3)for node in self.catalog.values()}
        if any(node.service not in self.breakers for node in self.catalog.values()):raise ValueError('breaker for every service required')
    @property
    def remaining(self):return self.record.call_budget-self.used
