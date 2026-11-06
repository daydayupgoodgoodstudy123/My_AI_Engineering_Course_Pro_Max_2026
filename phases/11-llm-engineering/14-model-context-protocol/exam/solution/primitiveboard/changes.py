"""Domain registration-change audit projection; real application and streaming are given."""
from .surface import descriptor
FIELD_ORDER={"tool":("name","description","inputSchema","annotations"),"resource":("uri","name","description"),"prompt":("name","description","arguments")}
def describe_change(view):
    """Return changed_fields in source descriptor order and descriptor-after evidence.

    Given ChangeView operation is add/update/remove and carries before/after Entry
    objects from actual kind-specific registration. Add/remove reports every field
    of that primitive kind. Update reports all and only unequal top-level source
    descriptor fields, with ordered nested arrays compared as ordered values.
    A remove artifact has descriptor=None; update/add has the exact after descriptor.
    Given driver owns identity, state changes, final manifest, framing and cadence.
    This local audit schema does not introduce MCP methods or notifications.
    """
    fields=FIELD_ORDER[view.kind]
    if view.operation=="remove":return {"changed_fields":list(fields),"descriptor":None}
    after=descriptor(view.after)
    if view.operation=="update":
        before=descriptor(view.before);fields=tuple(name for name in fields if before[name]!=after[name])
    return {"changed_fields":list(fields),"descriptor":after}
