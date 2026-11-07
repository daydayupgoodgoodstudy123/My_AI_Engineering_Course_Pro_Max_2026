"""Complete lexical intake, callable catalog, receipt consumer and last-K predicate."""
import re
from .models import Agent,Transfer
class RoutineCatalog:
    def __init__(self,agents):
        self._agents={a.name:a for a in agents}
        if len(self._agents)!=len(agents):raise ValueError('unique routine names')
        for a in agents:
            if len({f.name for f in a.functions})!=len(a.functions):raise ValueError('unique tools per routine')
    def agent(self,name):return self._agents[name]
    def function(self,owner,name):
        agent=self.agent(owner.name)
        return next(f for f in agent.functions if f.name==name)
    def names(self):return tuple(self._agents)
    def transfer_target(self,agent):
        """Rebind registered control targets; use the declared first safe routine for a removed target."""
        return self._agents.get(agent.name,next(iter(self._agents.values())))
def order_token(text):
    match=re.search(r'(?<![A-Za-z0-9_])[0-9]+(?![A-Za-z0-9_])',text)
    return match.group(0)if match else None
def refund_lookup(order_id,orders):return orders[order_id]
def refund_receipt(request,orders):return(request.order_id,refund_lookup(request.order_id,orders))
def origin_card(receipt):return(receipt.call_id,receipt.sender,receipt.target)
def is_two_agent_ring(edges):
    if len(edges)!=3:return False
    a,b,c=edges
    return(a.sender!=a.target and a.sender==c.sender==b.target and a.target==c.target==b.sender)
def invoke_bound(bound):return bound.function.invoke(**dict(bound.call.arguments))
