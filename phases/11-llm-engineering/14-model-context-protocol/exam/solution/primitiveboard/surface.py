"""Compile source-shaped three-primitive descriptors and typed result payloads."""
import copy
from .contracts import ordered_entries,capabilities,complete,json_text
def descriptor(entry):
    """Project exactly the source fields for one kind, without invoking a handler.

    Tool: name/description/inputSchema/annotations(destructiveHint true or {}).
    Resource: uri/name/description. Prompt: name/description/ordered arguments
    [{name,required:True}]. Return independent JSON field containers.
    """
    spec=entry.spec
    if spec.kind=="tool":return {"name":spec.name,"description":spec.description,"inputSchema":copy.deepcopy(spec.input_schema),"annotations":{"destructiveHint":True} if spec.destructive else {}}
    if spec.kind=="resource":return {"uri":spec.uri,"name":spec.name,"description":spec.description}
    return {"name":spec.name,"description":spec.description,"arguments":[{"name":name,"required":True} for name in spec.arguments]}
def compile_surface(entries):
    """Return deterministic per-kind descriptors and given source-true capabilities.

    Correct per-kind identity ordering and capabilities are supplied, including
    support for all three primitives when their catalogs happen to be empty.
    No transport/metadata handshake, authorization, cache implementation or MRTR.
    """
    return {"tools":[descriptor(entry) for entry in ordered_entries(entries,"tool")],"resources":[descriptor(entry) for entry in ordered_entries(entries,"resource")],"prompts":[descriptor(entry) for entry in ordered_entries(entries,"prompt")],"capabilities":capabilities()}
def project_result(entry,output):
    """Wrap a correctly invoked/validated primitive result using the source shape.

    Tool content[] text is JSON encoding of output plus isError=False. Resource
    contents[] has its exact URI/text and source text/plain mime type. Prompt
    messages[] contains one user text content. Given complete() owns resultType,
    server identity and source cache metadata (resource read only here).
    """
    if entry.spec.kind=="tool":return complete({"content":[{"type":"text","text":json_text(output)}],"isError":False})
    if entry.spec.kind=="resource":return complete({"contents":[{"uri":entry.spec.uri,"mimeType":"text/plain","text":output}]},True)
    return complete({"messages":[{"role":"user","content":{"type":"text","text":output}}]})
