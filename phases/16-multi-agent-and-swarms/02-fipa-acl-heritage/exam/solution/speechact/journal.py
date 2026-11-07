"""Append-only local ACL journals; optional empty metadata is present data."""
from .models import ACLMessage,message_value
from .values import pack_value,unpack_value
from .journal_support import append_record,read_records
class ACLJournal:
    def __init__(self,path):self.path=path
    def append(self,message):
        """Append a complete message; preserve optional None versus empty strings.

        Preserve original agent/text/correlation identities, exact payload values
        and order. Supplied tags and binary framing handle numeric/UTF8 details.
        """
        message_value(message)
        envelope={key:getattr(message,key) for key in ("performative","sender","receiver","language","ontology")}
        for key in ("protocol","conversation_id","reply_with"):
            value=getattr(message,key)
            if value is not None:envelope[key]=value
        append_record(self.path,{"envelope":envelope,"payload":pack_value(message.content)})
    def read_all(self):
        """Reopen all messages in append order, restoring opaque language labels."""
        rows=[]
        for record in read_records(self.path):
            e=record["envelope"]
            rows.append(message_value(ACLMessage(e["performative"],e["sender"],e["receiver"],unpack_value(record["payload"]),e["language"],e["ontology"],e.get("protocol"),e.get("conversation_id"),e.get("reply_with"))))
        return rows
