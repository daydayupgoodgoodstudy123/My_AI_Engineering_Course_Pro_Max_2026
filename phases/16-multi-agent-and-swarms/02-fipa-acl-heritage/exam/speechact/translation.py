"""Local source-shaped MCP translations; no request or URI is executed."""
from .models import ACLMessage
def translate_acl(request):
    """Map a supplied tools/call fixture to request with its original arguments."""
    return ACLMessage("inform","host","tool-server",request["params"].get("arguments",{}),"JSON",request["params"]["name"],"fipa-request",f"jsonrpc-{request['id']}",f"msg-{request['id']}")
def mcp_resources_read_to_acl(request):
    """Map resources/read raw URI to query-ref with source language URI."""
    return ACLMessage("query-ref","host","resource-server",request["params"]["uri"],"JSON","mcp-resource","fipa-query",f"jsonrpc-{request['id']}",f"msg-{request['id']}")
