"""Complete global edge identity/forest intake and actual P3 sealed-decision binding, not path or deposit algorithms."""
import math
from .models import LearningDecision
class GraphCatalog:
    def __init__(self,edges,decisions):
        self.edges={e.uid:e for e in edges};self.decisions={d.outcome_uid:d for d in decisions};self.vertices={v for e in edges for v in(e.source,e.target)}
        if len(self.edges)!=len(edges)or len(self.decisions)!=len(decisions):raise ValueError('unique global edge and decision identities required')
        if any(not isinstance(d,LearningDecision)for d in decisions):raise TypeError('actual typed P3 decision required')
    def edge(self,uid):return self.edges[uid]
    def decision(self,uid):return self.decisions[uid]
    def validate(self,roots,state,rho,floor):
        if not math.isfinite(rho)or not 0<=rho<=1 or not math.isfinite(floor)or floor<0:raise ValueError('finite graph decay domain required')
        if len(set(state.applied_epochs))!=len(state.applied_epochs)or any(type(e)is not int or e<0 for e in state.applied_epochs):raise ValueError('unique nonnegative graph epochs required')
        keys=[(t.task_type,t.destination,t.edge_uid)for t in state.trails]
        if len(set(keys))!=len(keys)or any(t.edge_uid not in self.edges or not math.isfinite(t.weight)or t.weight<0 for t in state.trails):raise ValueError('unique finite declared graph trail state required')
        keyset=set(keys);ids=set();paths=set();allocations=set();upper=0.
        def walk(node):
            nonlocal upper
            if node.uid in ids:raise ValueError('unique finite expedition forest required')
            ids.add(node.uid)
            for p in node.own_paths:
                d=self.decision(p.decision_uid)
                if p.uid in paths or d.allocation_uid in allocations or p.start not in self.vertices or p.destination not in self.vertices or any(e not in self.edges for e in p.edges):raise ValueError('one finite declared ant path per unique allocation and bound edges required')
                if type(p.epoch)is not int or p.epoch<0 or p.epoch!=d.epoch:raise ValueError('path epoch must bind its actual sealed outcome')
                if d.task_type is not None and any((d.task_type,p.destination,e)not in keyset for e in p.edges):raise ValueError('complete declared task-destination edge trails required')
                if not math.isfinite(d.amount)or d.amount<0:raise ValueError('finite nonnegative sealed amount required')
                upper+=d.amount*len(p.edges)
                if not math.isfinite(upper):raise ValueError('conservative representable graph credit required')
                paths.add(p.uid);allocations.add(d.allocation_uid)
            for child in node.children:walk(child)
        for root in roots:walk(root)
        if any(not math.isfinite(max(t.weight,floor)+upper)for t in state.trails):raise ValueError('conservative representable graph credit required')
