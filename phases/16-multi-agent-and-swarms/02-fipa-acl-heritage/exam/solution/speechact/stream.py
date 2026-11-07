"""Domain ACL envelope framing across decoded text chunks; outer driver is supplied."""
from .stream_driver import publish_envelopes
class ACLFramer:
    def __init__(self):self.parts=[];self.depth=0;self.quoted=False;self.escaped=False
    def feed(self,text):
        """Return each complete envelope in this chunk. Parentheses inside JSON
        quotes are data; escapes and quoted state persist across feed calls.
        Whitespace between envelopes is ignored. Never emit an incomplete frame.
        """
        completed=[]
        for char in text:
            if not self.parts:
                if char.isspace():continue
                if char!="(":raise ValueError("ACL opening delimiter")
            self.parts.append(char)
            if self.quoted:
                if self.escaped:self.escaped=False
                elif char=="\\":self.escaped=True
                elif char=='"':self.quoted=False
            elif char=='"':self.quoted=True
            elif char=="(":self.depth+=1
            elif char==")":
                self.depth-=1
                if self.depth==0:completed.append("".join(self.parts));self.parts=[]
        return completed
    def finish(self):
        """Reject trailing incomplete local ACL envelopes at end of input."""
        if self.parts or self.depth or self.quoted or self.escaped:raise ValueError("incomplete ACL envelope")
async def stream_envelopes(source):
    """Given publication/UTF8/close adapter around the candidate domain framer."""
    output=publish_envelopes(source,ACLFramer())
    try:
        async for envelope in output:yield envelope
    finally:await output.aclose()
