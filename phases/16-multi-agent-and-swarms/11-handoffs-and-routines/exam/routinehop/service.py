"""Complete single-intake and typed handoff replay service; no batch interpreter here."""
from .models import AskForOrder,TransferRequest,ReplayReport
from .intake import prepare_refund_request,make_transfer_receipt
from .guard import LastKLoopGuard
from .support import refund_receipt
class IntakeDesk:
    def __init__(self,orders):self.orders=orders;self.refund_calls=[]
    def refund(self,text):
        request=prepare_refund_request(text)
        if isinstance(request,AskForOrder):return request
        receipt=refund_receipt(request,self.orders)
        self.refund_calls.append(request.order_id)
        return receipt
class ReplayDesk:
    def replay(self,run_id,observations):
        """Consume every real observation and retain every receipt even after a loop exit."""
        guard=LastKLoopGuard();audit=[];receipts=[];stopped=[];first=None
        for index,observation in enumerate(observations):
            if isinstance(observation,TransferRequest):
                event=make_transfer_receipt(observation.call_id,observation.sender,observation.target,observation.tool)
                receipts.append(event)
            else:event=observation
            audit.append(event);exit_now=guard.observe(event,audit);stopped.append(exit_now)
            if exit_now and first is None:first=index
        return ReplayReport(run_id,tuple(audit),tuple(receipts),tuple(stopped),first)
