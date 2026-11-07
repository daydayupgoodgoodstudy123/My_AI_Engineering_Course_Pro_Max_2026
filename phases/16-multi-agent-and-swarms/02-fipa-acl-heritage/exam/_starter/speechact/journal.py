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
        raise NotImplementedError("append")
    def read_all(self):
        """Reopen all messages in append order, restoring opaque language labels."""
        raise NotImplementedError("read_all")
