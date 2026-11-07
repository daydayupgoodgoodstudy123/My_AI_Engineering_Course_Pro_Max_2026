"""Domain ACL envelope framing across decoded text chunks; outer driver is supplied."""
from .stream_driver import publish_envelopes
class ACLFramer:
    def __init__(self):self.parts=[];self.depth=0;self.quoted=False;self.escaped=False
    def feed(self,text):
        """Return each complete envelope in this chunk. Parentheses inside JSON
        quotes are data; escapes and quoted state persist across feed calls.
        Whitespace between envelopes is ignored. Never emit an incomplete frame.
        """
        raise NotImplementedError("feed")
    def finish(self):
        """Reject trailing incomplete local ACL envelopes at end of input."""
        raise NotImplementedError("finish")
async def stream_envelopes(source):
    """Given publication/UTF8/close adapter around the candidate domain framer."""
    output=publish_envelopes(source,ACLFramer())
    try:
        async for envelope in output:yield envelope
    finally:await output.aclose()
