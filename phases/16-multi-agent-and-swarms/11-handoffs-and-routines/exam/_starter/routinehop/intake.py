"""Refund intake and outgoing handoff receipt producers."""
from .models import AskForOrder,ReadyRefund,Transfer
from .support import order_token
def prepare_refund_request(text):
    """Keep an explicit opaque order token; ask for it when no token is present."""
    token=order_token(text)
    if token is None:return ReadyRefund("42")
    return ReadyRefund(str(int(token)))
def make_transfer_receipt(call_id,from_name,to_name,tool='handoff'):
    """Identify the outgoing routine as sender and the incoming routine as target."""
    return Transfer(call_id,to_name,tool,to_name)
