"""Compile source-shaped three-primitive descriptors and typed result payloads."""
import copy
from .contracts import ordered_entries,capabilities,complete,json_text
def descriptor(entry):
    """Project exactly the source fields for one kind, without invoking a handler.

    Tool: name/description/inputSchema/annotations(destructiveHint true or {}).
    Resource: uri/name/description. Prompt: name/description/ordered arguments
    [{name,required:True}]. Return independent JSON field containers.
    """
    raise NotImplementedError
def compile_surface(entries):
    """Return deterministic per-kind descriptors and given source-true capabilities.

    Correct per-kind identity ordering and capabilities are supplied, including
    support for all three primitives when their catalogs happen to be empty.
    No transport/metadata handshake, authorization, cache implementation or MRTR.
    """
    raise NotImplementedError
def project_result(entry,output):
    """Wrap a correctly invoked/validated primitive result using the source shape.

    Tool content[] text is JSON encoding of output plus isError=False. Resource
    contents[] has its exact URI/text and source text/plain mime type. Prompt
    messages[] contains one user text content. Given complete() owns resultType,
    server identity and source cache metadata (resource read only here).
    """
    raise NotImplementedError
