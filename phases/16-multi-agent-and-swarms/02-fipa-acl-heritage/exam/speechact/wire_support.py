"""Given finite envelope grammar/parser and quotes; not SL or full FIPA syntax."""
import json
from .models import ACLMessage,message_value
from .values import pack_value,unpack_value
BASE=("sender","receiver","content","language","ontology")
OPTIONAL=(("protocol","protocol"),("conversation-id","conversation_id"),("reply-with","reply_with"))
def quoted(text):return json.dumps(text,ensure_ascii=False)
def wire_fields(message):
    message_value(message)
    pairs=[(key,json.dumps(pack_value(message.content),ensure_ascii=False,separators=(",",":"),allow_nan=False) if key=="content" else getattr(message,key)) for key in BASE]
    pairs.extend((wire,getattr(message,field)) for wire,field in OPTIONAL if getattr(message,field) is not None)
    return pairs
def parse_envelope(text):
    """Parse one complete envelope: act plus :field JSON-string values only."""
    decoder=json.JSONDecoder();n=len(text);i=0
    def ws(pos):
        while pos<n and text[pos].isspace():pos+=1
        return pos
    i=ws(i)
    if i>=n or text[i]!="(":raise ValueError("ACL opening delimiter")
    i+=1;start=i
    while i<n and not text[i].isspace() and text[i]!=")":i+=1
    act=text[start:i];fields={}
    while True:
        i=ws(i)
        if i>=n:raise ValueError("incomplete ACL envelope")
        if text[i]==")":i=ws(i+1);break
        if text[i]!=":":raise ValueError("ACL field label")
        i+=1;start=i
        while i<n and not text[i].isspace():i+=1
        key=text[start:i];i=ws(i)
        if key in fields or i>=n or text[i]!='"':raise ValueError("ACL quoted field")
        value,i=decoder.raw_decode(text,i)
        if type(value) is not str:raise ValueError("ACL string field")
        fields[key]=value
    if i!=n or not set(BASE)<=set(fields) or not set(fields)<=set(BASE)|{key for key,_ in OPTIONAL}:raise ValueError("complete local ACL fields")
    message=ACLMessage(act,fields["sender"],fields["receiver"],unpack_value(json.loads(fields["content"])),fields["language"],fields["ontology"],*(fields.get(wire) for wire,_ in OPTIONAL))
    return message_value(message)
