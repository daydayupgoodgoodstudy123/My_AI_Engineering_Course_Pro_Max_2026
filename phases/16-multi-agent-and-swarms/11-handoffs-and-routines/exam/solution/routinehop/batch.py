"""Owner-bound flat tool batches and true Agent-valued control returns."""
from .models import BoundCall,Agent,AgentReturn,DataReturn,CallResult,CallSkipped,CallFailed,BatchReport,ToolFailure
from .support import invoke_bound
from .intake import make_transfer_receipt
def bind_batch_owner(active,calls,catalog):
    """Resolve every call upfront in the original owner namespace, including the later skipped tail.

    All calls name tools of this original routine; lookup is the supplied catalog boundary.
    """
    return tuple(BoundCall(active,call,catalog.function(active,call.tool))for call in calls)
def interpret_raw_tool_return(value):
    """A real Agent transfers control; text and strict JSON value trees remain data."""
    return AgentReturn(value)if isinstance(value,Agent)else DataReturn(value)
def run_batch(active,calls,catalog):
    """Execute the original owner's calls until first transfer; explicitly skip all remaining effects."""
    bound=bind_batch_owner(active,calls,catalog);receipts=[];current=active;transferred=False
    for item in bound:
        call=item.call
        if transferred:
            receipts.append(CallSkipped(call.call_id,item.owner.name,call.tool));continue
        try:value=invoke_bound(item)
        except ToolFailure as error:
            receipts.append(CallFailed(call.call_id,item.owner.name,call.tool,str(error)));continue
        outcome=interpret_raw_tool_return(value)
        if isinstance(outcome,AgentReturn):
            target=catalog.transfer_target(outcome.agent)
            receipts.append(make_transfer_receipt(call.call_id,item.owner.name,target.name,call.tool))
            current=target;transferred=True
        else:receipts.append(CallResult(call.call_id,item.owner.name,call.tool,outcome.value))
    return BatchReport(active.name,current,tuple(receipts))
