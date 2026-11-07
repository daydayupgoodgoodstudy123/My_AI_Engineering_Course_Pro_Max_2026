"""Finite quoted local ACL envelopes and complete UTF8 wire output."""
from .wire_support import wire_fields,quoted
def render_acl(message):
    """Render every field as a JSON-quoted string inside one local ACL envelope."""
    pairs=wire_fields(message);fields=[]
    for name,value in pairs:fields.append(f":{name} "+'"'+value+'"')
    return f"({message.performative} "+" ".join(fields)+")"
def encode_acl(message):
    """Return the entire rendered local envelope as exact UTF8 bytes."""
    text=render_acl(message)
    output=b""
    for char in text:output+=char.encode("utf-8")
    return output
