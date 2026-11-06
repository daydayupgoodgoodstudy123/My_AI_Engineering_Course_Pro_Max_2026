"""Export full paths from explicit local catalogs and their three primitive kinds."""
from .contracts import validate_catalog,scoped_admission,identity
from .surface import descriptor
def export_catalog(root):
    """Visit own entries and children in preorder with each complete catalog path.

    Local CatalogNode hierarchy is a teaching input extension, not federation or
    a multi-server tool routing namespace. Names may repeat under different parents.
    Preserve entry order and kind, including resources keyed by exact URI. The
    correct supplied scoped_admission checks duplicate(kind,identity) only within
    one complete local catalog path. Shape/cycle validation is supplied; do not
    reimplement it. Return each original handler reference with its descriptor.
    """
    validate_catalog(root);rows=[];seen=set()
    def visit(node,parent):
        path=parent+(node.name,)
        for entry in node.entries:
            scoped_admission(seen,path,entry)
            rows.append({"catalog_path":path,"kind":entry.spec.kind,"identity":identity(entry.spec),"descriptor":descriptor(entry),"handler":entry.handler})
        for child in node.children:visit(child,path)
    visit(root,())
    return tuple(rows)
