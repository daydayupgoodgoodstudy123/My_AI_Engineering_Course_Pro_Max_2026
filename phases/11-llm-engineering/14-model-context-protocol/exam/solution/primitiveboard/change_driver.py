"""Given real local change application and correct asynchronous NDJSON artifact driver."""
import json
from .contracts import ChangeView,slot_key
from .registry import Catalog
from .surface import compile_surface
from .changes import describe_change
def apply_registration(catalog,change):
    key=slot_key(change.spec);before=catalog.get(key)
    if change.operation=="upsert":
        catalog.register(change.spec);after=catalog.get(key);operation="add" if before is None else "update"
    elif change.operation=="remove":
        catalog.remove(key);after=None;operation="remove"
    else:raise ValueError("registration operation")
    return ChangeView(key[0],key[1],operation,before,after)
async def publish_changes(changes,handlers):
    """Publish one complete current change artifact, then the final complete surface.

    This is a local artifact stream, not an MCP JSON-RPC method or transport.
    Pull-through, actual current identity, JSON framing and source close are given.
    """
    catalog=Catalog(handlers);iterator=changes.__aiter__()
    try:
        async for change in iterator:
            view=apply_registration(catalog,change)
            payload={"type":"change","kind":view.kind,"identity":view.identity,"operation":view.operation}
            payload.update(describe_change(view))
            yield json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n"
        yield json.dumps({"type":"manifest","surface":compile_surface(catalog.entries())},ensure_ascii=False,separators=(",",":"))+"\n"
    finally:
        close=getattr(iterator,"aclose",None)
        if close is not None:await close()
