"""Complete invitation and memory-feature inspection; no composite rank or reflection implementation."""
from . import primitives
from .models import Inspection
from .support import validate_request,deliver_invitation,inspect_agent
class TownDesk:
    def inspect(self,request):
        validate_request(request)
        positions=primitives.invitation_recipients(request.population,request.sender_uid)
        population,delivered=deliver_invitation(request.population,positions,request)
        feature=primitives.prepare_query(request.query)
        agents=tuple(inspect_agent(a,request,feature,primitives)for a in population)
        return Inspection(request,delivered,agents)
