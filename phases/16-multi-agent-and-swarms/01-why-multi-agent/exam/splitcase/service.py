"""Given public replay facade; no model, network, delay or random call is executed."""
from .routing import specialist_input
from .usage import record_call_usage
from .view_support import required_fact_value
from .models import Receipt,CallRequest,design_value

class ReplayService:
    def preview(self,role,task,shared_facts,messages,private_notes,required):
        view=specialist_input(role,task,shared_facts,messages,private_notes)
        return view,required_fact_value(view,required)
    def record(self,request):
        """Retain the full immutable request and declared fixture output with its usage."""
        return Receipt(request,record_call_usage(request))

def prepare_design(design):
    """Given earlier-stage integration: project each call then record its real fixture use."""
    design_value(design);roles={role.name:role for role in design.roles};service=ReplayService();receipts=[]
    for call in design.calls:
        role=roles[call.role]
        view=specialist_input(role,call.task,call.shared_facts,call.messages,call.private_notes)
        request=CallRequest(call.call_id,call.role,role.system_prompt,view.user,call.output,call.output_tokens,call.tool_calls,view.facts)
        receipts.append(service.record(request))
    return tuple(receipts)
