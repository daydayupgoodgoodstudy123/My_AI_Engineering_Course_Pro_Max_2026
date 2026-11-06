"""Registration keeps each primitive callable and its local kind-specific identity."""
from .contracts import Entry,copy_spec,slot_key,compile_inventory,resolve_handler,admit_entry
def make_entry(spec,handlers):
    """Produce a descriptor with a callable reference; registration/discovery run no action."""
    return Entry(copy_spec(spec),resolve_handler(spec.handler_name,handlers))
class Catalog:
    def __init__(self,handlers):self.handlers=handlers;self._entries={};self._compiled=None
    def register(self,spec):
        """Register or replace one kind-scoped identity, retaining its real handler.

        Tools/prompts use name; resources use exact URI. Human resource names do
        not determine identity. A replacement keeps the original insertion slot.
        Inventory is a complete sorted immutable identity/handler-reference view.
        """
        entry=make_entry(spec,self.handlers)
        admit_entry(entry)
        key=slot_key(spec)
        self._entries[key]=entry
        self._compiled=None
    def inventory(self):
        if self._compiled is None:self._compiled=compile_inventory(self._entries.values())
        return self._compiled
    def entries(self):return tuple(self._entries.values())
    def get(self,key):return self._entries.get(key)
    def remove(self,key):
        del self._entries[key];self._compiled=None
def register_batch(specs,handlers):
    """Given public registration path; return a complete catalog and consumed inventory."""
    catalog=Catalog(handlers)
    for spec in specs:catalog.register(spec)
    return catalog,catalog.inventory()
