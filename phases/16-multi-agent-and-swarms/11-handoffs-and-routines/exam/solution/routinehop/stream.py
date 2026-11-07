"""Per-receipt public domain projection; classification and async driver are supplied."""
from .wire_support import receipt_kind
class ReceiptProjection:
    def payload(self,receipt):
        """Project each receipt's own identity and typed domain fields without inventing tool output."""
        kind=receipt_kind(receipt)
        if kind=='reply':return{'kind':kind,'sender':receipt.sender,'content':receipt.content}
        common={'kind':kind,'call_id':receipt.call_id,'tool':receipt.tool}
        if kind=='transfer':return dict(common,sender=receipt.sender,target=receipt.target)
        common['owner']=receipt.owner
        if kind=='call-result':common['result']=receipt.value
        elif kind=='call-skipped':common['reason']=receipt.reason
        else:common['error']=receipt.error
        return common
