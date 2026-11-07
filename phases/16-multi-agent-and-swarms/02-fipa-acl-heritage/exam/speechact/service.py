"""Given consumers distinguish a speech act, language label and opaque wire data."""
import json
from .translation import translate_acl,mcp_resources_read_to_acl
from .codec import encode_acl
from .wire_support import parse_envelope
def reply_obligation(message):
    obligations={message.conversation_id:message.reply_with} if message.performative=="request" else {}
    return obligations[message.conversation_id]
def consume_language_payload(message):
    if message.language=="JSON":return json.loads(message.content)
    if message.language=="URI":return message.content
    return message.content
class SpeechService:
    def require_tool_reply(self,request):
        message=translate_acl(request)
        return reply_obligation(message)
    def forward_resource_read(self,request):
        message=mcp_resources_read_to_acl(request)
        return consume_language_payload(message)
    def roundtrip(self,message):
        wire=encode_acl(message)
        return wire,parse_envelope(wire.decode("utf-8"))
